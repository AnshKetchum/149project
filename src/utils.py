import time
import cv2 as cv
import numpy as np
import math

from individual.actor import IndividualNode
from central.vision import Actor, Environment

def main():
    image = cv.imread("img/test_screen-kopi.png")
    rgb = [66, 56, 47]
    UtilityFunctions.get_color_range(image, rgb)

# Environment dimensions in centimeters
dimensions = (92, 62.5)
environment_width_cm = dimensions[0]
environment_height_cm = dimensions[1]

# Variables to store selected points and polygon
temp_frame = None
video_capture_mode = 1
points = []
grid_size = 50  # Initial grid size
polygon = []  # To store the polygon points for object tracking
tracking = False
polygon_complete = False
phase = 1  # Tracks the current phase

# Environment dimensions in centimeters
dimensions = (92, 62.5)
environment_width_cm = dimensions[0]
environment_height_cm = dimensions[1]
environment = Environment(grid_size)

def add_actor_to_environment(frame, polygon, name: str):

    # Grab physical actor coordinates
    x_coords = [p[0] for p in polygon]
    y_coords = [p[1] for p in polygon]
    min_x, max_x = min(x_coords), max(x_coords)
    min_y, max_y = min(y_coords), max(y_coords)
    bbox = (min_x, min_y, max_x - min_x, max_y - min_y)

    # Define actor methods 
    actor = None 

    if name.startswith('robot'):
        if IndividualNode.can_connect(name):
            print("Creating physical robot", name)
            actor = IndividualNode(name=name)
        else: 
            print("Failed to create robot")

    elif name.startswith('action'):
        print("Creating action point", name)
        actor = Actor(name=name)
    else:
        print("Creating misc actor", name)
        actor = Actor(name=name)

    if actor is not None:
        actor.initialize_tracker(frame, bbox)
        environment.add_actor(actor)


class UtilityFunctions:

    YELLOW=(255,255,153)
    RED=(0,0,255)
    GREEN=(0,255,0)
    BLUE=(255,0,0)
    ROBOT_ONE="robot 1"
    ROBOT_TWO="robot 2"
    ROBOT_ONE_RANGE = ((100, 150, 0), (140, 255, 255))
    ROBOT_TWO_RANGE = ((4, 53, 50), (24, 93, 86))
    TEXT_DISTANCE = 65

    @staticmethod
    def find_corners_feed(cap):
        
        points = []
        def click_event(event, x, y, flags, param):

            if event == cv.EVENT_LBUTTONDOWN:
                points.append((x, y))
                print(f"Point {len(points)}: {x}, {y}")
                cv.circle(temp_frame, (x, y), 5, (0, 0, 255), -1)
                cv.imshow("Video Feed", temp_frame)

        cv.namedWindow("Video Feed")
        cv.setMouseCallback("Video Feed", click_event)
        while len(points) < 4:
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame")
                break
            temp_frame = frame.copy()
            cv.imshow("Video Feed", frame)
            if cv.waitKey(1) & 0xFF == ord('q'):
                cap.release()
                cv.destroyAllWindows()
                exit()
        
        rectangles = UtilityFunctions.make_rectangle(points)
        corners = {
            UtilityFunctions.TOP_LEFT: rectangles[0], 
            UtilityFunctions.TOP_RIGHT: rectangles[1],
            UtilityFunctions.BOTTOM_LEFT: rectangles[2],
            UtilityFunctions.BOTTOM_RIGHT: rectangles[3],
        }

        points = sorted(points, key=lambda p: (p[1], p[0]))
        if points[0][0] > points[1][0]:
            points[0], points[1] = points[1], points[0]
        if points[2][0] > points[3][0]:
            points[2], points[3] = points[3], points[2]
            
        src_points = np.array(points, dtype=np.float32)
        dst_points = np.array([
            [0, 0],
            [frame.shape[1], 0],
            [0, frame.shape[0]],
            [frame.shape[1], frame.shape[0]]
        ], dtype=np.float32)

        H, _ = cv.findHomography(src_points, dst_points)
        return corners, H
    
    
    @staticmethod
    def euclidean_distance(point1, point2):
            return math.sqrt((point2[0] - point1[0]) ** 2 + (point2[1]-point1[1]) ** 2)    
    
    @staticmethod
    # Function to apply affine transformation to a point
    def apply_affine_transform(point, matrix):
        point_homogeneous = np.array([point[0], point[1], 1], dtype=np.float32)
        transformed = np.dot(matrix, point_homogeneous)
        x, y, w = transformed[0], transformed[1], transformed[2]
        if w != 0:  # Normalize by w for perspective transformations
            x /= w
            y /= w
        return x, y, w
    
    @staticmethod
    def apply_inverse_affine_transform(pixel_pos, matrix):
        # Invert the affine matrix
        inv_matrix, _ = cv.invert(matrix)
        
        # Apply the inverse transformation
        pixel_homogeneous = np.array([pixel_pos[0], pixel_pos[1], 1], dtype=np.float32)
        transformed = np.dot(inv_matrix, pixel_homogeneous)
        x, y, w = transformed[0], transformed[1], transformed[2]
        
        if w != 0:  # Normalize by w for perspective transformations
            x /= w
            y /= w
        return int(x), int(y)

    TOP_LEFT = "top_left" 
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    
    @staticmethod
    def compute_affine_transformation(corners, grid_width, grid_height):
        # Define the source (grid coordinates) and destination (image coordinates) points for affine transformation
        source_points = np.float32([
            [0, 0],  # Top-left of grid
            [grid_width-1, 0],  # Top-right of grid
            [0, grid_height-1],  # Bottom-left of grid 
            [grid_width-1, grid_height-1],  # Bottom-right of grid 
        ])
        dest_points = np.float32([
            corners[UtilityFunctions.TOP_LEFT], 
            corners[UtilityFunctions.TOP_RIGHT],
            corners[UtilityFunctions.BOTTOM_LEFT],
            corners[UtilityFunctions.BOTTOM_RIGHT],
        ])
        matrix,_ = cv.findHomography(source_points, dest_points)

        return matrix
    
    GREEN_RANGE = ((35, 50, 50), (85, 255, 255))
    RED_RANGE_1 = ((0, 70, 50), (10, 255, 255))
    RED_RANGE_2 = ((170, 70, 50), (180, 255, 255))

    tracking = False 
    def click_event(event, x, y, flags, param):
        global points, polygon, tracking, polygon_complete

        if event == cv.EVENT_LBUTTONDOWN:
            if not tracking:
                points.append((x, y))
                print(f"Point {len(points)}: {x}, {y}")
                cv.circle(temp_frame, (x, y), 5, (0, 0, 255), -1)
                cv.imshow("Video Feed", temp_frame)

    @staticmethod
    def find_corners(image):
        color_ranges = {
            "green": UtilityFunctions.GREEN_RANGE, 
            "red": UtilityFunctions.RED_RANGE_1,
        }

        # Find the corners of the maze
        corners_found = False
        while not corners_found:
            try:
                points = UtilityFunctions.find_points(image, color_ranges)
                corners = list(points.values())
                rectangles = UtilityFunctions.make_rectangle(corners) 
                corners_found = True
            except:
                print("Corners not found, trying again...")
                time.sleep(3)  # Try again if the corners are not found,
                continue

        corners = {
            UtilityFunctions.TOP_LEFT: rectangles[0], 
            UtilityFunctions.TOP_RIGHT: rectangles[1],
            UtilityFunctions.BOTTOM_LEFT: rectangles[2],
            UtilityFunctions.BOTTOM_RIGHT: rectangles[3],
        }
        return corners
    
    @staticmethod
    def make_rectangle(points):
        if len(points) != 4:
            raise ValueError("You must provide exactly 4 coordinates.")
        
        sorted_coords = sorted(points, key=lambda p: (p[1], p[0]))  # Sort by y first (top-to-bottom), then by x (left-to-right)
        
        # First two are top points (smallest y values)
        top_left = min(sorted_coords[:2], key=lambda p: p[0])  # Left-most 
        top_right = max(sorted_coords[:2], key=lambda p: p[0])  # Right-most 
        
        # Last two are bottom points (largest y values)
        bottom_left = min(sorted_coords[2:], key=lambda p: p[0])  # Left-most 
        bottom_right = max(sorted_coords[2:], key=lambda p: p[0])  # Right-most

        return top_left, top_right, bottom_left, bottom_right 

    @staticmethod
    def find_points(image, color_ranges):
        image = cv.GaussianBlur(image, (5, 5), 0)
        hsv = cv.cvtColor(image, cv.COLOR_BGR2HSV)

        points = {}
        for color_name, (lower, upper) in color_ranges.items():
            # lower, upper = UtilityFunctions.adjust_hsv_range(hsv, lower, upper)
            contours = UtilityFunctions.find_contours(hsv, lower, upper, color_name == "red")

            centroids = []
            for contour in contours:
                try:
                    cx, cy, area = UtilityFunctions.find_center_of_contour(contour)
                    if cx is not None:
                        centroids.append((cx, cy, area))
                except:
                    continue
            centroids = sorted(centroids, key=lambda x: x[2], reverse=True)
            best_centroid = centroids[0] if len(centroids) > 1 else None
            if best_centroid is None:
                print(f"Couldn't find 2 {color_name}: centroid/corner")
            points[f"{color_name}_1"] = centroids[0][:2]
            points[f"{color_name}_2"] = centroids[1][:2]
        return points   
    
    @staticmethod
    def find_center_of_contour(contour):
        M = cv.moments(contour)
        if M["m00"] != 0:  # Avoid division by zero
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            area = cv.contourArea(contour)  # Calculate the area of the contour

            return cx, cy, area
        return None
    @staticmethod
    def adjust_hsv_range(hsv, lower, upper):
        v_mean = np.mean(hsv[:, :, 2])  # Compute the mean brightness (value channel)
        adjustment = max(0, 255 - v_mean) // 10  # Scale the adjustment
        lower = np.array(lower) - [0, 0, adjustment]  # Lower the value range
        upper = np.array(upper) + [0, 0, adjustment]  # Increase the value range
        return np.clip(lower, 0, 255), np.clip(upper, 0, 255)

    @staticmethod
    def find_contours(hsv, lower, upper, red=False):
        # Create mask for the color
        lower = np.array(lower, dtype="uint8")
        upper = np.array(upper, dtype="uint8")
        mask = cv.inRange(hsv, lower, upper)
        if red:
            mask = cv.inRange(hsv, UtilityFunctions.RED_RANGE_1[0], 
                              UtilityFunctions.RED_RANGE_1[1]) | cv.inRange(hsv, UtilityFunctions.RED_RANGE_2[0], UtilityFunctions.RED_RANGE_2[1])

        # Find contours for the color
        contours, _ = cv.findContours(mask, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
        return contours
    
    @staticmethod
    def find_center_of_rectangle(positions):
        top_left = positions[0]
        bottom_right = positions[2]

        center_x = (top_left[0] + bottom_right[0]) // 2 
        center_y = (top_left[1] + bottom_right[1]) // 2 
        
        return (center_x,center_y)

    @staticmethod
    def kahan_sum(numbers):
        total = 0.0     
        c = 0.0         

        for num in numbers:
            y = num - c     
            t = total + y   
            c = (t - total) - y  
            total = t      

        return total    
    

    @staticmethod
    def get_all_objects(cap):
        global temp_frame
        global points, polygon, tracking, polygon_complete, phase

        def click_event(event, x, y, flags, param):
            global temp_frame
            global points, polygon, tracking, polygon_complete, phase

            if event == cv.EVENT_LBUTTONDOWN:
                if not tracking and phase == 0:
                    points.append((x, y))
                    print(f"Point {len(points)}: {x}, {y}")
                    cv.circle(temp_frame, (x, y), 5, (0, 0, 255), -1)
                    cv.imshow("Video Feed", temp_frame)

                elif phase == 1 and tracking:
                    if not polygon_complete:
                        polygon.append((x, y))
                        print(f"Polygon point {len(polygon)}: {x}, {y}")
                        if len(polygon) > 1:
                            cv.line(temp_frame, polygon[-2], polygon[-1], (255, 255, 0), 2)
                        cv.circle(temp_frame, (x, y), 5, (255, 255, 0), -1)

                        if len(polygon) > 2 and np.linalg.norm(np.array(polygon[0]) - np.array(polygon[-1])) < 10:
                            polygon_complete = True
                            cv.line(temp_frame, polygon[-1], polygon[0], (255, 255, 0), 2)
                            print("Polygon completed.")

                            name = str(input("\nEnter a name for the entity")).strip()

                            add_actor_to_environment(frame, polygon, name)

                            polygon.clear()
                            print("Added new actor", name)

                        cv.imshow("Original Video Feed", temp_frame)

                elif phase == 2:  # Orientation point selection
                    if environment.actors:
                        actor = environment.actors[-1]  # Assign orientation to the last added actor
                        actor.set_orientation_point((x, y))
                        print(f"Orientation point for {actor.name}: {x}, {y}")

        cv.namedWindow("Video Feed")
        cv.setMouseCallback("Video Feed", click_event)

        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame")
                break

            temp_frame = frame.copy()
            mapped_frame = frame.copy() #cv.warpPerspective(frame, H, (frame.shape[1], frame.shape[0]))
            for x in range(0, mapped_frame.shape[1], environment.get_grid_size()):
                cv.line(mapped_frame, (x, 0), (x, mapped_frame.shape[0]), (255, 0, 0), 1)
            for y in range(0, mapped_frame.shape[0], environment.get_grid_size()):
                cv.line(mapped_frame, (0, y), (mapped_frame.shape[1], y), (255, 0, 0), 1)
            for x in range(0, mapped_frame.shape[1], environment.get_grid_size()):
                for y in range(0, mapped_frame.shape[0], environment.get_grid_size()):
                    cv.circle(mapped_frame, (x, y), 2, (0, 255, 0), -1)
            for actor in environment.actors:
                if actor.update(frame):
                    top_left = (int(actor.bbox[0]), int(actor.bbox[1]))
                    bottom_right = (int(actor.bbox[0] + actor.bbox[2]), int(actor.bbox[1] + actor.bbox[3]))
                    cv.rectangle(mapped_frame, top_left, bottom_right, (0, 255, 255), 2)

                    # Draw orientation arrow
                    if actor.orientation is not None:
                        center = tuple(map(int, actor.get_location()))
                        arrow_length = 50
                        end_x = int(center[0] + arrow_length * np.cos(np.radians(actor.orientation)))
                        end_y = int(center[1] + arrow_length * np.sin(np.radians(actor.orientation)))
                        cv.arrowedLine(mapped_frame, center, (end_x, end_y), (0, 0, 255), 2)
                    
                    # Display actor name at the center of the bounding box
                    if actor.name:
                        text_size = cv.getTextSize(actor.name, cv.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                        text_x = int(actor.bbox[0] + actor.bbox[2] / 2 - text_size[0] / 2)
                        text_y = int(actor.bbox[1] + actor.bbox[3] / 2 + text_size[1] / 2)
                        cv.putText(mapped_frame, actor.name, (text_x, text_y), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)


            cv.imshow("Original Video Feed", frame)
            cv.imshow("Mapped Video Feed", mapped_frame)
            key = cv.waitKey(1) & 0xFF
            if key == ord('q'):
                cv.destroyAllWindows()
                return { v.name : v for v in environment.actors}
            elif key == ord('n'):
                tracking = not tracking
                polygon_complete = False
                polygon = []
            elif key == ord('a'):
                environment.update_grid_size(environment.get_grid_size() + 10)
            elif key == ord('b'):
                environment.update_grid_size(max(10, environment.get_grid_size() - 10))
            elif key == ord('r'):
                environment.reset_bounding_boxes()
            elif key == ord('o'):
                phase = 2  # Switch to orientation point selection phase





if __name__ == '__main__':
    main()