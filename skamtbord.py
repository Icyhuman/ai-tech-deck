import sys
import math
import os
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import QPainter, QPixmap, QTransform, QGuiApplication


class Skateboard(QWidget):
    def __init__(self):
        super().__init__()

        # Window setup
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.resize(700, 300)

        # Lock to bottom-right corner
        screen = QGuiApplication.primaryScreen().geometry()
        self.move(screen.width() - self.width(), screen.height() - self.height())

        # Load image

        base_dir = os.path.dirname(__file__)
        img_path = os.path.join(base_dir, "skateboard.png")

        self.image = QPixmap(img_path)

        self.qimage = self.image.toImage()

        print("Image loaded:", not self.image.isNull())
        solid = self.get_solid_points()
        self.hitbox_poly = self.convex_hull(solid)
        # Physics (now relative to window)
        self.pos = QPointF(200, 150)
        self.vel = QPointF(0, 0)
        self.angle = 0
        self.omega = 0
        self.grounded = False

        self.last_mouse_pos = None

        # Loop
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_physics)
        self.timer.start(16)

        self.show()


    def get_solid_points(self):
        points = []

        for y in range(self.qimage.height()):
            for x in range(self.qimage.width()):
                if self.qimage.pixelColor(x, y).alpha() > 10:
                    points.append((x, y))

        return points
    
    def convex_hull(self, points):
        points = sorted(set(points))

        if len(points) <= 1:
            return points

        def cross(o, a, b):
            return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])

        lower = []
        for p in points:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)

        upper = []
        for p in reversed(points):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)

        return lower[:-1] + upper[:-1]

    def is_point_on_board(self, local_pos):
        x = int(local_pos.x())
        y = int(local_pos.y())

        # Outside image bounds
        if x < 0 or y < 0 or x >= self.qimage.width() or y >= self.qimage.height():
            return False

        pixel = self.qimage.pixelColor(x, y)
        return pixel.alpha() > 10  # threshold (0–255)
    # --- Mouse interaction ---
    def mouseMoveEvent(self, event):
        current = event.pos()

        # --- Build transform (same as in paintEvent) ---
        transform = QTransform()
        transform.translate(self.pos.x() + self.image.width()/2,
                            self.pos.y() + self.image.height()/2)
        transform.rotate(self.angle)
        transform.translate(-self.image.width()/2,
                            -self.image.height()/2)

        # --- Invert transform ---
        inverted, ok = transform.inverted()
        if not ok:
            return

        # Map mouse into board-local space
        local_pos = inverted.map(current)

        # --- Hitbox check ---
        if not (0 <= local_pos.x() <= self.image.width() and
                0 <= local_pos.y() <= self.image.height()):
            self.last_mouse_pos = None
            return  # Ignore movement outside board
        if not self.is_point_on_board(local_pos):
            self.last_mouse_pos = None
            return

        # --- Flick logic ---
        if self.last_mouse_pos is not None:
            dx = current.x() - self.last_mouse_pos.x()
            dy = current.y() - self.last_mouse_pos.y()
            speed = math.hypot(dx, dy)

            if speed > 2:
                offset_x = local_pos.x() - self.image.width()/2

                if self.grounded:
                    # --- Pivot behavior ---
                    # Strong torque instead of translation
                    self.omega += offset_x * speed * 0.002

                    # Add a bit of upward motion (the "pop")
                    self.vel.setY(self.vel.y() - abs(offset_x) * 0.39)

                else:
                    # --- Air behavior (normal) ---
                    self.vel += QPointF(dx * 0.3, dy * 0.3)
                    self.omega += offset_x * 0.01

        self.last_mouse_pos = current

    def leaveEvent(self, event):
        self.last_mouse_pos = None

    def point_in_polygon(self, x, y, poly):
        inside = False
        n = len(poly)

        j = n - 1
        for i in range(n):
            xi, yi = poly[i]
            xj, yj = poly[j]

            intersect = ((yi > y) != (yj > y)) and \
                        (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi)

            if intersect:
                inside = not inside

            j = i

        return inside

    def get_transformed_corners(self):
        transform = QTransform()
        transform.translate(self.pos.x() + self.image.width()/2,
                            self.pos.y() + self.image.height()/2)
        transform.rotate(self.angle)
        transform.translate(-self.image.width()/2,
                            -self.image.height()/2)

        corners = [
            QPointF(0, 0),
            QPointF(self.image.width(), 0),
            QPointF(self.image.width(), self.image.height()),
            QPointF(0, self.image.height())
        ]

        return [transform.map(c) for c in corners]
    
    def get_world_poly(self):
        transform = QTransform()
        transform.translate(self.pos.x() + self.image.width()/2,
                            self.pos.y() + self.image.height()/2)
        transform.rotate(self.angle)
        transform.translate(-self.image.width()/2,
                            -self.image.height()/2)

        return [transform.map(QPointF(x, y)) for x, y in self.hitbox_poly]
    # --- Physics ---
    def update_physics(self):
        self.pos += self.vel
        self.angle += self.omega

        self.vel *= 0.95
        self.omega *= 0.95

        target_angle = round(self.angle / 180) * 180

        # Smooth interpolation
        self.angle += (target_angle - self.angle) * 0.2

        # --- POLYGON IN WORLD SPACE ---
        poly = self.get_world_poly()

        min_x = min(p.x() for p in poly)
        max_x = max(p.x() for p in poly)
        min_y = min(p.y() for p in poly)
        max_y = max(p.y() for p in poly)

        bounce = 0.7

        # --- FLOOR COLLISION (main improvement) ---
        if max_y > self.height():
            overlap = max_y - self.height()

            # push board up based on shape, not center
            self.pos.setY(self.pos.y() - overlap)

            # only damp vertical velocity
            self.vel.setY(-self.vel.y() * bounce)

            # IMPORTANT: add angular response (prevents "dead flat stop")
            self.omega += self.vel.x() * 0.01
        else:
            self.vel.setY(self.vel.y() + 0.3) 

        # --- LEFT / RIGHT WALLS ---
        if min_x < 0:
            overlap = 0 - min_x
            self.pos.setX(self.pos.x() + overlap)
            self.vel.setX(-self.vel.x() * bounce)

        if max_x > self.width():
            overlap = max_x - self.width()
            self.pos.setX(self.pos.x() - overlap)
            self.vel.setX(-self.vel.x() * bounce)

        self.update()

    # --- Render ---
    def paintEvent(self, event):
        painter = QPainter(self)

        transform = QTransform()
        transform.translate(self.pos.x() + self.image.width()/2,
                        self.pos.y() + self.image.height()/2)
        transform.rotate(self.angle)
        transform.translate(-self.image.width()/2,
                        -self.image.height()/2)

        painter.setTransform(transform)

        # Draw skateboard
        painter.drawPixmap(0, 0, self.image)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Skateboard()
    sys.exit(app.exec_())