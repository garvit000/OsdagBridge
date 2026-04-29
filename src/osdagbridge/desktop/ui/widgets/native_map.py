
import math
import json
from pathlib import Path
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QPoint, QPointF, QRectF
from PySide6.QtGui import QPainter, QPixmap, QBrush, QColor, QPen, QMouseEvent, QWheelEvent, QPainterPath

# Path to zone overlay images
_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "core" / "data" / "project_location"
INDIA_MAP_IMAGE = _DATA_DIR / "india_map.png"
SEISMIC_ZONE_IMAGE = _DATA_DIR / "seismic.png"
WIND_ZONE_IMAGE = _DATA_DIR / "wind.png"

# India bounding box (approximate) for overlay alignment
# These are the geographic bounds the overlay images represent
INDIA_BOUNDS = {
    "north": 35,  # Northern-most latitude
    "south": 6.5,   # Southern-most latitude
    "west": 68.0,   # Western-most longitude
    "east": 97.5,   # Eastern-most longitude
}

class NativeMapWidget(QWidget):
    """
    A native map widget that renders a local India map image using QPainter.
    It keeps the existing coordinate projection so map clicks, panning, zooming,
    and weather/zone lookups continue to use latitude and longitude.
    """
    locationSelected = Signal(float, float)  # Emits (lat, lon) on click

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        
        # Initial View (Center of India roughly)
        self.latitude = 20.5937
        self.longitude = 78.9629
        self.zoom = 5
        self.min_zoom = 4  # Restrict zoom out to keep focus on India
        self.max_zoom = 18
        
        # Marker (None initially, or set to a default)
        self.marker_lat = None
        self.marker_lon = None
        
        # Tile size
        self.tile_size = 256

        # Local raster map used instead of remote map tiles.
        self._base_map_pixmap = QPixmap(str(INDIA_MAP_IMAGE))

        # GeoJSON boundary overlay cache
        self._geojson_shapes = []  # list[tuple[list[(lon, lat)], closed]]
        self._geojson_visible = True
        
        # Interaction state
        self._last_mouse_pos = QPoint()
        self._is_panning = False
        self._mouse_press_pos = QPoint() # To distinguish click from pan

        # Overlay settings ("none", "seismic", "wind")
        self._overlay_type = "none"
        self._overlay_opacity = 0.5  # 50% opacity
        self._overlay_pixmap = None  # Cached QPixmap for the overlay

        # Initialize
        self.setMinimumSize(400, 300)
        self.load_geojson(_DATA_DIR / "india-osm.geojson")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # 1. Calculate center pixel in world coordinates
        center_px_x, center_px_y = self.lat_lon_to_pixel(self.latitude, self.longitude, self.zoom)
        
        # 2. Determine the top-left of the viewport in world pixels.
        view_x = center_px_x - width / 2
        view_y = center_px_y - height / 2

        # 3. Draw the local map raster.
        self.draw_base_map(painter, view_x, view_y)

        # 3.5. Draw zone overlay if active
        if self._overlay_type != "none" and self._overlay_pixmap:
            self._draw_zone_overlay(painter, view_x, view_y)

        # Draw GeoJSON administrative boundary on top of raster layers.
        if self._geojson_visible:
            self.draw_geojson(painter, view_x, view_y)
        
        # 4. Draw Marker (Pin) if it exists
        if self.marker_lat is not None and self.marker_lon is not None:
             marker_px_x, marker_px_y = self.lat_lon_to_pixel(self.marker_lat, self.marker_lon, self.zoom)
             screen_marker_x = marker_px_x - view_x
             screen_marker_y = marker_px_y - view_y
             
             # Draw simple pin
             painter.setBrush(QBrush(QColor(255, 0, 0)))
             painter.setPen(Qt.NoPen)
             # Circle head
             painter.drawEllipse(QPointF(screen_marker_x, screen_marker_y - 15), 8, 8)
             # Triangle pointing down
             path = QPainterPath()
             path.moveTo(screen_marker_x - 7, screen_marker_y - 11)
             path.lineTo(screen_marker_x + 7, screen_marker_y - 11)
             path.lineTo(screen_marker_x, screen_marker_y)
             path.closeSubpath()
             painter.drawPath(path)

        painter.end()

    def draw_base_map(self, painter: QPainter, view_x: float, view_y: float):
        """Draw the bundled India map image aligned to the configured India bounds."""
        painter.fillRect(self.rect(), QColor("#000000"))

        if self._base_map_pixmap.isNull():
            painter.setPen(QColor("#666666"))
            painter.drawText(self.rect(), Qt.AlignCenter, "India map image not found")
            return

        target_rect = self._india_bounds_screen_rect(view_x, view_y)
        source_rect = QRectF(self._base_map_pixmap.rect())
        painter.drawPixmap(target_rect, self._base_map_pixmap, source_rect)

    def _india_bounds_screen_rect(self, view_x: float, view_y: float) -> QRectF:
        """Return the screen rectangle occupied by India's geographic bounds."""
        nw_px_x, nw_px_y = self.lat_lon_to_pixel(
            INDIA_BOUNDS["north"], INDIA_BOUNDS["west"], self.zoom
        )
        se_px_x, se_px_y = self.lat_lon_to_pixel(
            INDIA_BOUNDS["south"], INDIA_BOUNDS["east"], self.zoom
        )

        return QRectF(
            nw_px_x - view_x,
            nw_px_y - view_y,
            se_px_x - nw_px_x,
            se_px_y - nw_px_y,
        )

    def load_geojson(self, path):
        """Load GeoJSON boundaries (FeatureCollection) for rendering."""
        self._geojson_shapes = []
        geojson_path = Path(path)
        if not geojson_path.exists():
            return

        try:
            with geojson_path.open("r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
        except (OSError, json.JSONDecodeError):
            return

        for feature in data.get("features", []):
            geometry = feature.get("geometry") or {}
            geom_type = geometry.get("type")
            coords = geometry.get("coordinates", [])

            if geom_type == "Polygon":
                for ring in coords:
                    self._geojson_shapes.append((ring, True))
            elif geom_type == "MultiPolygon":
                for polygon in coords:
                    for ring in polygon:
                        self._geojson_shapes.append((ring, True))
            elif geom_type == "LineString":
                self._geojson_shapes.append((coords, False))
            elif geom_type == "MultiLineString":
                for line in coords:
                    self._geojson_shapes.append((line, False))

        self.update()

    def draw_geojson(self, painter: QPainter, view_x: float, view_y: float):
        """Draw loaded GeoJSON boundary using map pixel projection."""
        if not self._geojson_shapes:
            return

        painter.save()
        pen = QPen(QColor("#092133"))
        pen.setWidth(3)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        for points, is_closed in self._geojson_shapes:
            if len(points) < 2:
                continue

            path = QPainterPath()
            first_lon, first_lat = points[0]
            first_px_x, first_px_y = self.lat_lon_to_pixel(first_lat, first_lon, self.zoom)
            path.moveTo(first_px_x - view_x, first_px_y - view_y)

            for lon, lat in points[1:]:
                px_x, px_y = self.lat_lon_to_pixel(lat, lon, self.zoom)
                path.lineTo(px_x - view_x, px_y - view_y)

            if is_closed:
                path.closeSubpath()

            painter.drawPath(path)

        painter.restore()

    def set_geojson_overlay_visible(self, visible: bool):
        """Toggle GeoJSON boundary rendering for performance."""
        self._geojson_visible = bool(visible)
        self.update()

    # --- Interaction ---
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_panning = True
            self._last_mouse_pos = event.pos()
            self._mouse_press_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_panning:
            delta = event.pos() - self._last_mouse_pos
            self._last_mouse_pos = event.pos()
            
            # Panning moves the map view provided we shift center opposite to mouse
            # Convert screen delta to world pixel delta
            self.pan_map(-delta.x(), -delta.y())

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_panning = False
            self.setCursor(Qt.ArrowCursor)
            
            # Check if it was a click (distance moved < threshold)
            dist = (event.pos() - self._mouse_press_pos).manhattanLength()
            if dist < 5:
                # Clicked! Place marker.
                self.place_marker_at_screen_pos(event.pos())

    def place_marker_at_screen_pos(self, screen_pos):
         # Convert screen click to world lat/lon
         width = self.width()
         height = self.height()
         
         center_px_x, center_px_y = self.lat_lon_to_pixel(self.latitude, self.longitude, self.zoom)
         view_x = center_px_x - width / 2
         view_y = center_px_y - height / 2
         
         click_px_x = view_x + screen_pos.x()
         click_px_y = view_y + screen_pos.y()
         
         lat, lon = self.pixel_to_lat_lon(click_px_x, click_px_y, self.zoom)
         
         self.marker_lat = lat
         self.marker_lon = lon
         self.locationSelected.emit(lat, lon)
         self.update()

    def wheelEvent(self, event: QWheelEvent):
        angle = event.angleDelta().y()
        if angle > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def zoom_in(self):
        new_zoom = min(self.zoom + 1, self.max_zoom)
        self.set_zoom(new_zoom)

    def zoom_out(self):
        new_zoom = max(self.zoom - 1, self.min_zoom)
        self.set_zoom(new_zoom)

    def set_zoom(self, new_zoom):
        if new_zoom != self.zoom:
            self.zoom = new_zoom
            self.update()

    def pan_map(self, dx_px, dy_px):
        # Convert pixel delta to lat/lon delta at current zoom
        center_px_x, center_px_y = self.lat_lon_to_pixel(self.latitude, self.longitude, self.zoom)
        
        new_px_x = center_px_x + dx_px
        new_px_y = center_px_y + dy_px
        
        self.latitude, self.longitude = self.pixel_to_lat_lon(new_px_x, new_px_y, self.zoom)
        
        # Clamp to India bounds to prevent navigating away
        self.latitude = max(min(self.latitude, INDIA_BOUNDS["north"] + 1.0), INDIA_BOUNDS["south"] - 1.0)
        self.longitude = max(min(self.longitude, INDIA_BOUNDS["east"] + 1.0), INDIA_BOUNDS["west"] - 1.0)
        
        self.update()

    # --- Math Helpers (Web Mercator) ---
    def lat_lon_to_pixel(self, lat, lon, zoom):
        n = 2 ** zoom
        # x
        x_norm = (lon + 180) / 360
        x_pixel = x_norm * n * self.tile_size
        
        # y
        lat_rad = math.radians(lat)
        # Avoid infinity at poles
        lat_rad = max(min(lat_rad, 1.4844), -1.4844) 
        
        y_norm = (1 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2
        y_pixel = y_norm * n * self.tile_size
        
        return x_pixel, y_pixel

    def pixel_to_lat_lon(self, x_pixel, y_pixel, zoom):
        n = 2 ** zoom
        
        # lon
        x_norm = x_pixel / (n * self.tile_size)
        lon = x_norm * 360 - 180
        
        # lat
        y_norm = y_pixel / (n * self.tile_size)
        n_inv_pi = math.pi * (1 - 2 * y_norm)
        state = math.atan(math.sinh(n_inv_pi))
        lat = math.degrees(state)
        
        return lat, lon


    def set_marker_location(self, lat, lon):
        """
        Sets the marker location programmatically and centers the map.
        This is useful for syncing when coordinates are entered manually.
        """
        self.marker_lat = lat
        self.marker_lon = lon
        self.latitude = lat
        self.longitude = lon
            
        self.locationSelected.emit(lat, lon) # Optional: emit signal if we want uniform behavior, 
                                             # but beware of infinite loops if connected to inputs!
                                             # Typically we don't emit if setting FROM the input.
                                             # We won't emit here to avoid loops.
        self.update()

    def set_overlay_type(self, overlay_type: str, opacity: float = 0.5):
        """
        Set the zone overlay to display on top of the map.
        
        Args:
            overlay_type: One of "none", "seismic", or "wind"
            opacity: Overlay opacity (0.0 to 1.0), default 0.5 (50%)
        """
        self._overlay_type = overlay_type.lower()
        self._overlay_opacity = max(0.0, min(1.0, opacity))
        
        if self._overlay_type == "seismic" and SEISMIC_ZONE_IMAGE.exists():
            self._overlay_pixmap = QPixmap(str(SEISMIC_ZONE_IMAGE))
        elif self._overlay_type == "wind" and WIND_ZONE_IMAGE.exists():
            self._overlay_pixmap = QPixmap(str(WIND_ZONE_IMAGE))
        else:
            self._overlay_pixmap = None
            self._overlay_type = "none"
        
        self.update()

    def _draw_zone_overlay(self, painter: QPainter, view_x: float, view_y: float):
        """
        Draw the zone overlay image on the map, aligned to India's geographic bounds.
        """
        if not self._overlay_pixmap or self._overlay_pixmap.isNull():
            return

        target_rect = self._india_bounds_screen_rect(view_x, view_y)
        
        # Skip drawing if completely outside viewport
        if (target_rect.right() < 0 or target_rect.left() > self.width() or
            target_rect.bottom() < 0 or target_rect.top() > self.height()):
            return
        
        # Set opacity
        painter.setOpacity(self._overlay_opacity)
        
        # Draw scaled overlay
        source_rect = QRectF(self._overlay_pixmap.rect())
        painter.drawPixmap(target_rect, self._overlay_pixmap, source_rect)
        
        # Reset opacity
        painter.setOpacity(1.0)
