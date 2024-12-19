import cv2 as cv
import networkx as nx
import numpy as np
import threading
import queue
import asyncio
import sys 
import os 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from SMrTa.MRTASolver import MRTASolver, Robot
from SMrTa.MRTASolver.objects import Task

from solver.graph import Graph as gr
from central.util import UtilityFunctions as uf


MOVE_DURATION_MS = 13  # 13 ms to move 1 cm
TURN_DURATION_MS = 50  # 50 ms to turn 45 degrees
DIAGONAL_MULTIPLIER = 1.414  # sqrt(2) for diagonal movement

class VideoToGraph:
    
    def initialize_tracker(self, cap):

        # Capture frame-by-frame
        ret, frame = self.cap.read()

        # if frame is read correctly ret is True
        if not ret:
            print("Can't receive frame (stream end?). Exiting ...")
            cap.release()
            cv.destroyAllWindows()
            exit()

        # Initialize a list for trackers and bounding boxes
        self.robot_trackers = []
        self.robot_bounding_boxes = []
        
        # Select multiple ROIs manually or programmatically
        while True:
            # Manually select bounding boxes
            bbox = cv.selectROI("Frame", frame, fromCenter=False, showCrosshair=True)
            self.robot_bounding_boxes.append(bbox)
            
            # Initialize a tracker for this bounding box
            tracker = cv.TrackerKCF.create()  # Change tracker type if needed
            tracker.init(frame, bbox)
            self.robot_trackers.append(tracker)
            
            # Ask user if they want to select more bounding boxes
            print("Press 'y' to select another object or any other key to continue")
            key = cv.waitKey(0)
            if key != ord('y'):
                break

            cv.destroyWindow("Frame")

    #initialize
    def __init__(self, height, length, video_file, robots, metric = True):

        # video feed
        self.cap = self.initialize_camera(video_file)

        # Display toggles
        self.display_grid = True
        self.display_paths = True
        self.display_obstacles = True
        self.display_qr_objects = True
        self.display_actions_points = True
        self.display_deadline = True
        self.display_HUD = False

        # Graph setup
        self.done_smt = False
        self.square_length_cm = length if metric else length * 2.54
        self.square_height_cm = height if metric else height * 2.54
        self.square_pixel_length = 0
        self.square_pixel_height = 0
        self.graph_x_nodes = 0
        self.graph_y_nodes = 0
        self.block_size_cm = 3
        self.pixel_conversion = []
        self.corners = {}
        self.matrix = any
        self.graph = nx.Graph()

        # shortest paths from robot to goal
        self.paths = {}
        self.robot_goals = {}
        self.deadline_threshold = 2000

        # QR Code tracking 
        self.qcd = None
        self.overlapping_nodes = set()
        self.tracked_qr_objects = {}

        # Robot tracking
        self.tracked_robots = {}
        self.robots_colors = {uf.ROBOT_ONE: (uf.ROBOT_ONE_RANGE), uf.ROBOT_TWO: (uf.ROBOT_TWO_RANGE)}
        self.robots = robots
        self.robot_trackers = []
        self.robot_bounding_boxes = []

        # relay processed video via thread to avoid creating a blocking call
        self.frame_queue = queue.Queue(maxsize=1)
        self.running = True
        self.thread = threading.Thread(target=self.start_environment, daemon=True)
        self.thread.start()
        self.overlay_update_frame_interval = 1

    # Video input
    def initialize_camera(self, camera = int(0)):
        capture = cv.VideoCapture(camera) # 0 is the default camera, can also take a file

        if not capture.isOpened():
            print("Cannot open camera")
            exit()

        return capture
    
    # Release the camera 
    def tear_down(self):
        self.running = False
        self.cap.release()
        try:
            self.thread.join()
        except:
            print("Thread couldn't be joined")
        cv.destroyAllWindows()

    def has_robot_position(self, name):
        return name in self.tracked_robots
        
    def get_robot_positions(self, robot):
        center = self.tracked_robots[robot].get_location()
        return center

    def get_action_point(self, action_point):
        action_point = self.tracked_qr_objects[action_point] if self.tracked_qr_objects.__contains__(action_point) else None
        return action_point
    
    def get_nearest_node_to_actionpoint(self, action_point):
    
        action_point = self.get_action_point(action_point)
        if action_point is None:
            return None
        print(action_point)
        center = uf.find_center_of_rectangle(action_point)
        return gr.find_nearest_node(self.graph, center)

    def run_solver(self, actions, robots):
        # create and get the necessary input for mrta solver
        graph = self.graph
        paths = self.paths

        print("graph: ", graph)
        print("paths: ", paths)
        try:
            gr.print_path_weights(graph, paths[uf.ROBOT_TWO])
        except Exception as e:
            print(e)

        agents = []

        for i, r in enumerate(robots):
            agents.append(
                Robot(id=i, start = gr.find_nearest_node(self.graph, r.get_location()))
            )
        
        # Insanely high number, 
        deadline = 100000000
        tasks = []

        for i in range(1, len(actions) - 1):
            tasks.append(
                Task(id = i, 
                     start=gr.find_nearest_node(self.graph, actions[i-1].get_location()),
                     end=gr.find_nearest_node(self.graph, actions[i].get_location()),
                     deadline=deadline
                     )
            )
        
        tasks.append(Task(
            id = len(tasks),
            start=gr.find_nearest_node(self.graph, actions[-1].get_location()),
            end=gr.find_nearest_node(self.graph, actions[0].get_location()),
            deadline=deadline
        ))
            

        tasks_stream = [[tasks, 0]]
        self.agents = agents
        self.tasks = tasks

        # Ensure elements are added as the last element
        ap_set = []
        for a in agents:
            if a.start not in ap_set:
                ap_set.append(a.start)
        for t in tasks:
            if t.start not in ap_set:
                ap_set.append(t.start)
            if t.end not in ap_set:
                ap_set.append(t.end)

        self.action_points = ap_set
        num_aps = len(self.action_points)
        print("Action points: ", ap_set)
        print("Action points: ", self.action_points)

        # Remap agent and task start/end indices into the action_points indices [0, len(action_points)-1], leaving self.action_points containing the intersection id of the action point
        for a in agents:
            a.start = self.action_points.index(a.start)

        for t in tasks:
            t.start = self.action_points.index(t.start)
            t.end = self.action_points.index(t.end)

        solver_size = len(self.action_points)
        solver_graph = np.ones((solver_size, solver_size)) * 10000
        for i in range(solver_size):
            for j in range(solver_size):
                if i == j:
                    solver_graph[i][j] = 0
                    solver_graph[j][i] = 0
                else:
                    try:
                        
                        path = gr.safe_astar_path(graph, self.action_points[i], self.action_points[j], gr.heuristic)
                        if path is None:
                            continue
                        print(path)
                        turning_cost = 0
                        movement_cost = gr.print_path_weights(graph, path)*MOVE_DURATION_MS//self.block_size_cm
                        # print(f"Movement cost: {movement_cost}")
                        # Add turning costs to edges along path
                        prev_direction = 0 # North
                        for src, dest in zip(path[:-1], path[1:]):
                            src_pos = graph.nodes[src].get(gr.GRID_POS)
                            dest_pos = graph.nodes[dest].get(gr.GRID_POS)
                            
                            # Calculate direction vector
                            dx = dest_pos[0] - src_pos[0]
                            dy = dest_pos[1] - src_pos[1]
                            
                            if dx == 0:
                                new_direction = 90 if dy > 0 else 270
                            elif dy == 0:
                                new_direction = 0 if dx > 0 else 180  
                            elif dx > 0:
                                new_direction = 45 if dy > 0 else 315
                            else:
                                new_direction = 135 if dy > 0 else 225
                                
                            angle_diff = abs(new_direction - prev_direction)
                            if angle_diff > 180:
                                angle_diff = 360 - angle_diff
                                
                            turning_cost += (angle_diff / 45) * TURN_DURATION_MS
                                
                            prev_direction = new_direction
                        total_cost = movement_cost + turning_cost
                        # print(f"Total cost: {total_cost}")
                        solver_graph[i][j] = int(total_cost)
                        solver_graph[j][i] = int(total_cost)
                        # print(solver_graph[i][j])
                    except Exception as e:
                        print(e)

        solver = MRTASolver(
            solver_name='z3',
            theory='QF_UFBV',
            agents=agents,
            tasks_stream=tasks_stream,
            room_graph=solver_graph.tolist(),
            capacity=1,
            num_aps=num_aps,
            aps_list=[num_aps],
            fidelity=1,
        )

        if solver.sol is None:
            print("No solution found!")
            return None
        
        print("FOUND SOLUTION", solver.sol)

        return solver.sol

    # Create and update graph from the video input
    def start_environment(self):
        frame_count = 0  # Count frames to update the overlay after a set number of frames
        refresh_graph = True  

        while self.running:

            # Capture frame-by-frame
            ret, frame = self.cap.read()

            # if frame is read correctly ret is True
            if not ret:
                print("Can't receive frame (stream end?). Exiting ...")
                self.running = False
                break

            if self.corners == {}:
                self.corners, self.H = uf.find_corners_feed(self.cap)

            # frame = cv.warpPerspective(frame, self.H, (frame.shape[1], frame.shape[0]))
            refresh_graph = True if frame_count % self.overlay_update_frame_interval*3 == 0 else False
            overlay_image = frame.copy()
            update = frame_count % self.overlay_update_frame_interval == 0
            
            if update:
                self.convert_image_to_graph(overlay_image, refresh_graph)


                #self.detect_qr_objects(overlay_image)
                refresh_graph = False
 
            
            if self.tracked_robots == {}:
                # Find all robots, actions, and grab the SMT solution
                self.tracked_robots = uf.get_all_objects(self.H, self.cap)

                actions = [ self.tracked_robots[a] for a in self.tracked_robots if a.startswith('action')]
                robots = [ self.tracked_robots[a] for a in self.tracked_robots if a.startswith('robot')]

                self.smt_solution = self.run_solver(actions, robots)
                self.smt_solution = self.convert_solution_to_schedules(self.smt_solution)
                self.smt_solution = self.generate_point_to_point_movement_instructions(self.smt_solution)
                self.done_smt = True

                self.smt_dict = {}

                for rob, sol in zip(robots, self.smt_solution):
                    self.smt_dict[rob.name] = {
                        'name' : rob.name,
                        'solution' : sol,
                        'robot' : rob
                    }

          
            self.update_robot_positions_from_trackers(frame)
            for i in range(len(self.robot_trackers)):
                self.draw_robot_position(overlay_image, i)

            # self.detect_robots(overlay_image, self.robots_colors)
            if self.display_grid:
                self.draw_grid(overlay_image, self.graph)

            if self.display_qr_objects:
                self.draw_qr_objects(overlay_image)

            if self.display_paths:
                pass
            
            if self.display_deadline:
                self.draw_deadline(overlay_image)            
            
            self.draw_HUD(overlay_image)

            # try:
            #     no_robots = self.no_robots()
            #     if no_robots:
            #         pass
            #     else:
            #         robot_1_center = self.tracked_robots[uf.ROBOT_ONE][1]
            #         robot_1 = gr.find_nearest_node(self.graph, robot_1_center)
            #         robot_2_center = self.tracked_robots[uf.ROBOT_TWO][1]
            #         robot_2 = gr.find_nearest_node(self.graph, robot_2_center)
            #         path = gr.safe_astar_path(self.graph, robot_1, robot_2, gr.heuristic)
            #         if path is not None and self.display_paths:
            #             overlay_image = gr.draw_transformed_path(overlay_image, self.graph, path)
            #             gr.print_path_weights(self.graph, path)
                    
                
                
            # except:
            #     if update:
            #         pass

            # Display the (frame + overlay)
            if not self.frame_queue.full():
                self.frame_queue.put(overlay_image)
            frame_count += 1

    def no_robots(self):
        return not self.tracked_robots.__contains__(uf.ROBOT_ONE) and not self.tracked_robots.__contains__(uf.ROBOT_TWO)

    def direction_to_turn(self, src, dest):
        if dest[1] == src[1] and dest[0] < src[0]:
            return 'N'
        elif dest[1] == src[1] and dest[0] > src[0]:
            return 'S'
        elif dest[0] == src[0] and dest[1] > src[1]:
            return 'E'
        elif dest[0] == src[0] and dest[1] < src[1]:
            return 'W'
        elif dest[0] > src[0] and dest[1] > src[1]:
            return 'SE'
        elif dest[0] > src[0] and dest[1] < src[1]:
            return 'NE'
        elif dest[0] < src[0] and dest[1] > src[1]:
            return 'SW'
        elif dest[0] < src[0] and dest[1] < src[1]:
            return 'NW'


    def generate_point_to_point_movement_instructions(self, robot_schedules):
        paths = []
        PICKUP_CMD = "P" # Do a spin
        DROPOFF_CMD = "D" # Do a spin
        FORWARD_CMD = "F"
        TURN_LEFT_CMD = "L"
        TURN_RIGHT_CMD = "R"
        WAIT_CMD = "W"
        instructions_set = []
        for i, rschedule in enumerate(robot_schedules):
            robot_id = "robot 1" if i == 0 else "robot 2"
            instructions = []
            prev_direction = None
            movement_start = False
            # print(f"Robot {robot_id} paths:")
            for i in range(len(rschedule)-1):
                src = rschedule[i]['location']
                dest = rschedule[i+1]['location']

                next_action = rschedule[i+1]['action']
                if i > 0 and next_action != "WAIT":
                    movement_start = True
                # Compute full path between src and dest
                path = gr.safe_astar_path(self.graph, self.graph.nodes[src].get(gr.GRID_POS), self.graph.nodes[dest].get(gr.GRID_POS), gr.heuristic)
                print(path)
                if self.paths.get(robot_id) is None:
                    self.paths[robot_id] = []
                self.paths[robot_id].append(path)

                if movement_start == False and gr.print_path_weights(self.graph, path) < rschedule[i+1]['time'] - rschedule[i]['time']:
                    instructions.append(f"{WAIT_CMD}:{int(rschedule[i+1]['time'] - rschedule[i]['time'] - gr.print_path_weights(self.graph, path))}")
                # print(path)

                if len(path) > 1:
                    step = 0
                    while step < len(path)-1:
                        direction = self.direction_to_turn(path[step], path[step + 1])
                        if prev_direction is not None and prev_direction != direction:
                            direction_angles = {
                                'N': 0,
                                'NE': 45,
                                'E': 90,
                                'SE': 135,
                                'S': 180,
                                'SW': 225,
                                'W': 270,
                                'NW': 315
                            }
                            angle = direction_angles[direction] - direction_angles[prev_direction]
                            if angle > 180:
                                angle = 360 - angle

                            angle = int(abs(angle))
                            if angle > 0:
                                instructions.append(f"{TURN_RIGHT_CMD}:{angle}")
                            elif angle < 0:
                                instructions.append(f"{TURN_LEFT_CMD}:{angle}")

                        j = 1
                        while (step + j < len(path)-1):
                            if self.direction_to_turn(path[step + j], path[step + j + 1]) == direction:
                                j += 1
                            else:
                                break

                        instructions.append(f"{FORWARD_CMD}:{j}")
                        step += j
                        prev_direction = direction

                # After movement
                if next_action == "PICKUP":
                    instructions.append(PICKUP_CMD)
                elif next_action == "DROPOFF":
                    instructions.append(DROPOFF_CMD)                        

            instructions_set.append(instructions)
            print(f"Robot {robot_id} Instructions: {instructions}")
        return instructions_set

    def convert_solution_to_schedules(self, solution):
        num_robots = len(solution['agt'])
        robot_schedules = []
        
        for robot_id in range(num_robots):
            schedule = []
            agent_data = solution['agt'][robot_id]

            for i in range(len(agent_data['t'])):
                time = agent_data['t'][i]
                action_id = agent_data['id'][i]

                location = None
                action_type = None
                task_num = None

                if action_id < num_robots:
                    # This is the agent's home/start location
                    location = self.action_points[action_id]
                    action_type = "WAIT"
                else:
                    # Task-related action
                    task_idx = (action_id - num_robots) // 2
                    is_pickup = ((action_id - num_robots) % 2 == 0)
                    if is_pickup:
                        action_type = "PICKUP"
                        location = self.action_points[self.tasks[task_idx].start]
                    else:
                        action_type = "DROPOFF"
                        location = self.action_points[self.tasks[task_idx].end]
                    task_num = task_idx

                if location is not None and action_type is not None:
                    schedule.append({
                        'time': time,
                        'location': location,
                        'action': action_type,
                        'task_id': task_num
                    })
            schedule.sort(key=lambda x: x['time'])
            robot_schedules.append(schedule)

        for robot_id, schedule in enumerate(robot_schedules):
            print(f"\nRobot {robot_id} Plan:")
            print("Time  | Location | Action  | Task")
            print("-" * 40)
            
            # for step in schedule:
            #     task_str = f"Task {step['task_id']}" if step['task_id'] is not None else "N/A"
            #     print(f"{step['time']:5d} | {step['location']:8d} | {step['action']:7s} | {task_str}") 
        return robot_schedules

    
    def convert_image_to_graph(self, image, refresh_graph):
        if refresh_graph:
            #corners = uf.find_corners(image)
            corners = self.corners
            # if self.corners != corners:
            self.corners = corners
            self.set_dimensions(self.corners)
            self.graph = nx.grid_2d_graph(self.graph_x_nodes, self.graph_y_nodes)
            gr.add_diagonal_edges(self.graph_x_nodes, self.graph_y_nodes, self.graph)
            self.refresh_matrix(self.corners)
            gr.set_node_positions(self.graph, self.matrix)
            self.update_robot_positions_from_trackers(image)
            self.detect_static_obstacles(image)
            # self.detect_qr_objects(image)
            # self.detect_robots(image, self.robots_colors)
            self.compute_pixel_conversion()
            gr.adjust_graph_weights(self.graph, self.pixel_conversion)        

        return self.graph
    
    def refresh_matrix(self, corners):
        matrix = uf.compute_affine_transformation(corners, self.graph_x_nodes, self.graph_y_nodes)
        self.matrix = matrix

    def draw_grid(self, image, graph):
        overlay_image = gr.draw_nodes_overlay(graph, image)
        overlay_image = gr.draw_edges_overlay(graph, overlay_image)
        # overlay_image = self.draw_corners_overlay(overlay_image)
        return overlay_image

    def draw_qr_objects(self, overlay_image):
        for i, key in enumerate(self.tracked_qr_objects.keys()):
            # print(i, key)
            actor = self.tracked_qr_objects[key]
            pts = np.array(actor.get_bbox())
            poly_pts = pts.reshape((-1, 1, 2))

            pts_loc = np.array(actor.get_location())

            # print(pts, pts[0])
            if key.startswith('action'):
                cv.polylines(overlay_image, poly_pts, isClosed=True, color=uf.YELLOW, thickness=2)
                cv.putText(overlay_image, f"Action point {key.strip('action')}", (pts[0][0]+20, pts[0][1]-20), cv.FONT_HERSHEY_SIMPLEX, 1.3, (0,0,0), 3)

    def draw_corners_overlay(self, overlay_image):
        max_y = max(self.corners.values(), key=lambda p: p[1])[1]
        for corner_name, (x,y) in self.corners.items():
            if y < max_y / 2:
                x += 50 # text position adjustment
                y -= 100 
            cv.putText(overlay_image, corner_name, (x-150, y+50), cv.FONT_HERSHEY_SIMPLEX, 1.5, (0,0,0), 3)
        return overlay_image
    
    def find_paths(self, robot_goal):
        paths = {}
        for robot, goal in robot_goal.items():
            try:
                _, center = self.tracked_qr_objects[robot]
            except:
                continue
            path = gr.a_star_from_pixel_pos(self.graph, center, goal)
            paths[robot] = path
        return paths

    def set_robot_goals(self, goals):
        for robot, goal in goals.items():
            self.robot_goals[robot] = goal

    def set_dimensions(self, corners):
        try:
            # Compute grid dimensions based on the block size and image size
            self.square_pixel_length = corners[uf.TOP_RIGHT][0] - corners[uf.TOP_LEFT][0]
            self.square_pixel_height = corners[uf.BOTTOM_RIGHT][1] - corners[uf.TOP_LEFT][1]

            pixel_block_height_px  = (self.block_size_cm / self.square_height_cm) * self.square_pixel_height
            pixel_block_length_px = (self.block_size_cm / self.square_length_cm) * self.square_pixel_length

            self.graph_x_nodes = int(self.square_pixel_length / pixel_block_length_px)
            self.graph_y_nodes = int(self.square_pixel_height / pixel_block_height_px)
        except:
            print("Couldn't set the dimensions")    

    def compute_pixel_conversion(self):
        try:
            self.pixel_conversion.append(self.square_length_cm / self.square_pixel_length)
            self.pixel_conversion.append(self.square_height_cm / self.square_pixel_height)
            self.pixel_conversion.append((self.square_length_cm**2 + self.square_height_cm**2) ** 0.5 / (self.square_pixel_length**2 + self.square_pixel_height**2) ** 0.5)
        except Exception as e:
            print(e)
            print("Couldn't compute pixel dimensions")

    def detect_static_obstacles(self, image, proximity_threshold=60):
        overlay_image = image.copy()
        hsv_image = cv.cvtColor(overlay_image, cv.COLOR_BGR2HSV)
        pink_lower = [140, 50, 50]
        pink_upper = [170, 255, 255]
        contours = uf.find_contours(hsv_image, pink_lower, pink_upper)

        MIN_CONTOUR_AREA = 3000
        filtered_contours = [cnt for cnt in contours if cv.contourArea(cnt) > MIN_CONTOUR_AREA]

        for contour in filtered_contours:
            cv.drawContours(overlay_image, [contour], -1, uf.RED, 2)
            gr.update_graph_based_on_obstacle(self.graph, contour, proximity_threshold)

    def update_robot_positions_from_trackers(self, image):

        # Update the trackers of each individual actor
        for actor_name in self.tracked_robots:
            # print("Updating actor", actor_name)
            actor = self.tracked_robots[actor_name]

            if actor.update(image):
                top_left = (int(actor.bbox[0]), int(actor.bbox[1]))
                bottom_right = (int(actor.bbox[0] + actor.bbox[2]), int(actor.bbox[1] + actor.bbox[3]))
                cv.rectangle(image, top_left, bottom_right, (0, 255, 255), 2)

                # Draw orientation arrow
                if actor.orientation is not None:
                    center = tuple(map(int, actor.get_location()))
                    arrow_length = 50
                    end_x = int(center[0] + arrow_length * np.cos(np.radians(actor.orientation)))
                    end_y = int(center[1] + arrow_length * np.sin(np.radians(actor.orientation)))
                    cv.arrowedLine(image, center, (end_x, end_y), (0, 0, 255), 2)

            # Track all robot actors 
            if actor.name in [uf.ROBOT_ONE, uf.ROBOT_TWO]:
                # print("Setting tracked QR robot objects to the respective value")
                self.tracked_qr_objects[actor_name] = actor    

            # Track all action points 
            elif actor.name.startswith('action'):
                # print("Setting tracked QR action points to the respective value")
                self.tracked_qr_objects[actor_name] = actor    


            # Track all action point locations 
            

        # for i, tracker in enumerate(self.robot_trackers):
        #     ok, bbox = tracker.update(image)
        #     if ok:
        #         # Draw bounding box
        #         # Tracking success
        #         (x, y, w, h) = [int(v) for v in bbox]
        #         top_left = (x, y)
        #         bottom_right = (x + w, y + h)
        #         center_x = (top_left[0] + bottom_right[0]) // 2 
        #         center_y = (top_left[1] + bottom_right[1]) // 2 
        #         center = (center_x, center_y)
        #         self.update_robot_position((bbox,center), i)
        #     else:
        #         # Tracking failure
        #         cv.putText(image, f"Tracking failed for Node {i}", (100, 50 + i * 30), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)


    def detect_robots(self, image, color_ranges):
        hsv_image = cv.cvtColor(image, cv.COLOR_BGR2HSV)
        robots = {}

        for robot, (lower, upper) in color_ranges.items():
            contours = uf.find_contours(hsv_image, lower, upper)
            MIN_CONTOUR_AREA = 6000
            largest_contour = max(contours, key=cv.contourArea)
            for cnt in contours:
                if cv.contourArea(cnt) > MIN_CONTOUR_AREA:
                    center = uf.find_center_of_contour(largest_contour)
                    if center is not None:
                        cx, cy,_ = center    
            robots[robot] = (largest_contour, (cx, cy))
        
        for robot, (contours, (cx,cy)) in robots.items():
            self.update_robot_position((contours, (cx,cy)), robot)
            image = self.draw_robot_position(image, robot)        

    def draw_robot_position(self, image, robot, outline_color = uf.GREEN,center_color = uf.RED):
        if robot in self.tracked_robots.keys():
            (bbox, center) = self.tracked_robots[robot]
            # cv.drawContours(image, [contours], -1, outline_color, 2)
            (x, y, w, h) = [int(v) for v in bbox]
            cv.rectangle(image, (x, y), (x + w, y + h), outline_color, 2)
            cv.circle(image, center, 7, center_color, -1)
            self.outline_text(image, f"robot {robot}", (center[0]-65, center[1]-20), color=uf.GREEN, scale=1.2, outline=4)
        return image

    def update_robot_position(self, bbox, robot):
        robot = robot if robot else None
        if robot:
            try:
                previous_position = self.tracked_robots[robot]
                same_position = np.array_equal(bbox[1], previous_position[1])
                if not same_position:
                    self.tracked_robots[robot] = bbox
            except:
                self.tracked_robots[robot] = bbox



    def detect_qr_objects(self, image):
        # Initialize the QR code detector
        self.qcd = cv.QRCodeDetector() if self.qcd is None else self.qcd

        gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
        _, thresh = cv.threshold(gray, 0, 255, cv.THRESH_BINARY | cv.THRESH_OTSU)
        
        # Detect and decode QR codes
        retval, decoded_infos, points, _ = self.qcd.detectAndDecodeMulti(thresh)
        
        if retval:
            for i, qr_code_info in enumerate(decoded_infos):
                # print("Received QR Code data of ", qr_code_info)
                pass 
                # self.update_position(points[i], qr_code_info)

        for key in self.tracked_qr_objects.keys():
            try:
                if key[0] == "a":
                    qr_code_points = self.tracked_qr_objects[key].astype(int)
                    overlapping_nodes = self.check_qr_code_overlap(self.graph, qr_code_points)
                    gr.update_graph_based_on_qr_code(self.graph, overlapping_nodes, self.overlapping_nodes)
                    self.overlapping_nodes = overlapping_nodes
            except:
                pass 
                # print(f"Invalid QR code detected: {key}")
    
    def check_qr_code_overlap(self, graph, qr_code_points, proximity_threshold=25):
        # Get the bounding box of the QR code in graph space
        min_x = min([pt[0] for pt in qr_code_points])
        max_x = max([pt[0] for pt in qr_code_points])
        min_y = min([pt[1] for pt in qr_code_points])
        max_y = max([pt[1] for pt in qr_code_points])
        
        # Check for nodes within the bounding box
        overlapping_nodes = gr.find_nodes_within_bounding_box(graph, min_x, max_x, min_y, max_y, proximity_threshold)    
        return overlapping_nodes
    
    def update_position(self, position, qr_object):
        qr_object = qr_object if qr_object else self.get_nearest_object(position)
        if qr_object:
            try:
                previous_position = self.tracked_qr_objects[qr_object]
                same_position = np.array_equal(position, previous_position)
                if not same_position:
                    self.tracked_qr_objects[qr_object] = position
            except:
                self.tracked_qr_objects[qr_object] = position

    def get_nearest_object(self, points, threshold=400):
        closest_id = None
        min_distance = gr.INF
        center_position = uf.find_center_of_rectangle(points)

        for obj_id, last_positions in self.tracked_qr_objects.items():
            last_position_center = uf.find_center_of_rectangle(last_positions)
            distance = (uf.euclidean_distance(center_position, last_position_center))
            if distance < min_distance and distance < threshold:
                min_distance = distance
                closest_id = obj_id

        return closest_id
    
    def display_robot_instructions(self, overlay_image, instructions):
        pos_x, pos_y = self.get_corner_position_for_text(multiplier=9)
        for (robot, instruction) in instructions:
            overlay_image = self.outline_text(overlay_image, f"{robot}: {instruction}", (pos_x, pos_y), color=uf.GREEN, scale=1.2, outline=4)
            pos_y += uf.TEXT_DISTANCE

    def draw_deadline(self, overlay_image):
        if self.display_deadline:
            pos_x, pos_y = self.get_corner_position_for_text(multiplier=6)
            self.outline_text(overlay_image, f"Deadline threshold: {self.deadline_threshold}", (pos_x, pos_y), color=uf.GREEN, scale=1.2, outline=4)
    
    def draw_HUD(self, overlay_image):
        pos_x, pos_y = self.get_corner_position_for_text(multiplier=20)
        if self.display_HUD:
            overlay_image = self.outline_text(overlay_image, f"Grid: {self.display_grid}", (pos_x, pos_y), scale=1.2,outline=4)
            overlay_image = self.outline_text(overlay_image, f"Paths: {self.display_paths}", (pos_x, pos_y - 1*uf.TEXT_DISTANCE), scale=1.2,outline=4)
            overlay_image = self.outline_text(overlay_image, f"Action points: {self.display_actions_points}", (pos_x, pos_y - 2*uf.TEXT_DISTANCE), scale=1.2,outline=4)
            overlay_image = self.outline_text(overlay_image, f"Deadline threshold: {self.display_deadline}", (pos_x, pos_y - 3*uf.TEXT_DISTANCE), scale=1.2,outline=4)
            overlay_image = self.outline_text(overlay_image, f"QR objects: {self.display_qr_objects}", (pos_x, pos_y - 4*uf.TEXT_DISTANCE), scale=1.2,outline=4)
            overlay_image = self.outline_text(overlay_image, f"Obstacles: {self.display_obstacles}", (pos_x, pos_y - 5*uf.TEXT_DISTANCE), scale=1.2,outline=4)

        overlay_image = self.outline_text(overlay_image, f"Options: {self.display_HUD}", (pos_x, pos_y+uf.TEXT_DISTANCE), scale=1.2,outline=4)

    def get_corner_position_for_text(self, x = 10, y = 20, multiplier = 1):
        pos_x, pos_y = (self.corners[uf.TOP_LEFT][0]) // x, (self.square_pixel_height // y) * multiplier 
        return (pos_x, pos_y)

    def overlay_text(self, image, text, position, color=(0,0,0), scale=1.3):
        cv.putText(image, text, position, cv.FONT_HERSHEY_SIMPLEX, scale, (color), thickness=2, lineType=cv.LINE_AA)
        return image
    
    def outline_text(self, image, text, position, color=(255,255,255), scale=1.3, outline=2):
        font = cv.FONT_HERSHEY_SIMPLEX
        color_outline = (0, 0, 0)  # Black outline

        cv.putText(image, text, position, font, scale, color_outline, outline, lineType=cv.LINE_AA)
        cv.putText(image, text, position, font, scale, color, outline-2, lineType=cv.LINE_AA)
        return image

    def check_weights(self):
        length = gr.safe_astar_path(self.graph, (0,0), (self.graph_x_nodes-1,0), gr.heuristic)
        height = gr.safe_astar_path(self.graph, (0,0), (0, self.graph_y_nodes-1), gr.heuristic)
        diagonal = gr.safe_astar_path(self.graph, (0,0), (self.graph_x_nodes - 1 , self.graph_y_nodes-1), gr.heuristic)

        print("Length, height, diagonal")
        gr.print_path_weights(self.graph, length)
        gr.print_path_weights(self.graph, height)
        gr.print_path_weights(self.graph, diagonal)

def main():
    video = "img/video/test_red_close.mov"
    vg = VideoToGraph(75, 150, video)
    vg.start_environment()
    vg.tear_down()

if __name__ == "__main__":
    main()