import cv2 as cv 
from collections import deque
import numpy as np


# Actor class to define a simple object being tracked by central node vision
class Actor:
    def __init__(self, name):
        self.name = name
        self.tracker = cv.TrackerCSRT_create()
        self.bbox = None
        self.history = deque(maxlen=300)
        self.origin = None
        self.orientation = None  # Angle in degrees
        self.orientation_point = None  # Point indicating orientation

    def initialize_tracker(self, frame, bbox):
        self.bbox = bbox
        self.tracker.init(frame, bbox)

    def update(self, frame):
        success, new_bbox = self.tracker.update(frame)
        if success:
            self.bbox = tuple(map(int, new_bbox))
            self.history.append(self.get_location())
            if self.orientation_point:
                self.update_orientation(frame)
        return success

    def get_location(self):
        if not self.bbox:
            return None
        x, y, w, h = self.bbox
        center_x = x + w / 2
        center_y = y + h / 2
        return center_x, center_y

    def set_orientation_point(self, point):
        self.orientation_point = point
        self.update_orientation_from_point()

    def update_orientation_from_point(self):
        if self.bbox and self.orientation_point:
            center = self.get_location()
            if center:
                dx = self.orientation_point[0] - center[0]
                dy = self.orientation_point[1] - center[1]
                self.orientation = np.degrees(np.arctan2(dy, dx))

    def update_orientation(self, frame):
        if self.bbox:
            x, y, w, h = map(int, self.bbox)
            roi = frame[y:y+h, x:x+w]
            if roi.size > 0:
                gray = cv.cvtColor(roi, cv.COLOR_BGR2GRAY)
                _, binary = cv.threshold(gray, 50, 255, cv.THRESH_BINARY | cv.THRESH_OTSU)
                contours, _ = cv.findContours(binary, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
                if contours:
                    largest_contour = max(contours, key=cv.contourArea)
                    if len(largest_contour) >= 5:  # PCA requires at least 5 points
                        data = largest_contour.reshape(-1, 2).astype(np.float32)
                        mean, eigenvectors = cv.PCACompute(data, mean=None)
                        angle = np.arctan2(eigenvectors[0, 1], eigenvectors[0, 0])
                        self.orientation = np.degrees(angle)

    # def distance_from_origin_cm(self, frame, location):
    #     if not self.origin or not location:
    #         return 0
    #     origin_x, origin_y = self.origin
    #     loc_x, loc_y = location
    #     width_scale = environment_width_cm / frame.shape[1]
    #     height_scale = environment_height_cm / frame.shape[0]
    #     dx = (loc_x - origin_x) * width_scale
    #     dy = (loc_y - origin_y) * height_scale
    #     return np.sqrt(dx**2 + dy**2)

    def get_bbox(self):
        """Return bounding box coordinates in clockwise order starting from top-left."""
        if not self.bbox:
            return None
        x, y, w, h = self.bbox
        top_left = [x, y]
        top_right = [x + w, y]
        bottom_right = [x + w, y + h]
        bottom_left = [x, y + h]
        return [top_left, top_right, bottom_right, bottom_left]
    
    def intersects_with(self, other_bbox):
        """Check if this Actor's bounding box intersects with another bounding box."""
        if not self.bbox or not other_bbox:
            return False

        print("ours", self.bbox, "theirs", other_bbox)
        x1, y1, w1, h1 = self.bbox
        x2, y2, w2, h2 = other_bbox

        return not (x1 + w1 < x2 or x2 + w2 < x1 or y1 + h1 < y2 or y2 + h2 < y1)


# Environment class to manage actors and grid information
class Environment:
    def __init__(self, grid_size):
        self.actors = []
        self.grid_size = grid_size

    def add_actor(self, actor):
        self.actors.append(actor)

    def update_grid_size(self, new_grid_size):
        self.grid_size = new_grid_size

    def get_grid_size(self):
        return self.grid_size

    def reset_bounding_boxes(self):
        for actor in self.actors:
            actor.history.clear()
            actor.bbox = None
            actor.tracker.clear()

