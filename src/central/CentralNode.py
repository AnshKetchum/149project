import numpy as np
import VideoToGraph as v2g
import time
import cv2 as cv
from util import UtilityFunctions as uf
from Graph import Graph as gr
import sys  
import os 
from client import Robot as IndividualNode
import json 
from dotenv import load_dotenv
import requests

load_dotenv()

def main():
    web_cam_close = "img/video/webcam_red_close.mov"
    web_cam_further_angle = "img/video/webcam_red_further_angle.mov"
    web_cam_further_top = "img/video/webcam_red_further_top.mov"
    web_cam_distance = "img/video/center_test.mov"

    # Read robots
    with open('devices.json', 'r') as f:
        robots = json.load(f)['devices']

    video_feed = [web_cam_close, web_cam_further_angle, web_cam_further_top]

    e = os.environ["VIDEO_FEED"]
    print("Searching for env", e)
    video_feed = [int(os.getenv('VIDEO_FEED', 0))]
    for video_input in video_feed:
        driver_code(video_input, robots)
        print("Video feed completed: ", video_input)

def get_robot_configs(name):
    with open('devices.json', 'r') as f:
        dct = json.load(f)

        for d in dct['devices']:
            if d['name'] == name:
                return [d]

def driver_code(video_input, robots):
    solver_ran = False
    # parse the video adjust parameter to 0 to use webcam 
    central_node = CentralNode(video_input, robots)
    central_node.init()

    # Wait for the mapping to be completed
    while len(central_node.vg.corners) < 4:
        print("Waiting for corners to be detected")
        time.sleep(1)

    # Wait for all key objects to be recognized

    central_node.vg.overlay_update_frame_interval = 1
    last_time = time.time()
    
    while not central_node.vg.done_smt:
        print("Waiting for SMT to be detected")
        time.sleep(1)

    # 
    q = central_node.vg.tracked_qr_objects
    robots = [q[a] for a in q if a.startswith('robot') ]

    try:
        
        scheduled_tasks = {}
        while True:
            if not central_node.vg.frame_queue.empty():
                frame = central_node.vg.frame_queue.get()

                ### Stage 1 --> Robot Identification 
                # Identify which robots are currently alive in the environment
                pos1, pos2 = None, None
                    
                if central_node.vg.has_robot_position(uf.ROBOT_ONE):
                    pos1 = central_node.vg.get_robot_positions(uf.ROBOT_ONE)

                    # Once we have identified at least one robot, try to calibrate
                if central_node.vg.has_robot_position(uf.ROBOT_TWO):
                    pos2 = central_node.vg.get_robot_positions(uf.ROBOT_TWO)
                
                instructions = []#[(uf.ROBOT_ONE, [(0,0)]), (uf.ROBOT_TWO, [(1,1)])]

                if pos1:
                    instructions.append((uf.ROBOT_ONE, (float(pos1[0]), float(pos1[1]))))

                    print("Calibrating", central_node.tracking_robot(uf.ROBOT_ONE))
                    if not central_node.tracking_robot(uf.ROBOT_ONE):
                        robots = central_node.init_robots(get_robot_configs(uf.ROBOT_ONE))
                        central_node.robot_calibration_and_sync(robots)
                if pos2:
                    instructions.append((uf.ROBOT_TWO, (float(pos2[0]), float(pos2[1]))))
                    print("Calibrating", central_node.tracking_robot(uf.ROBOT_TWO))
                    if not central_node.tracking_robot(uf.ROBOT_TWO):
                        robots = central_node.init_robots(get_robot_configs(uf.ROBOT_TWO))
                        central_node.robot_calibration_and_sync(robots)

                # ### Stage 2 --> Action Point Scheduling
                # # Identify all key action points and available robots
                # q = central_node.vg.tracked_qr_objects
                # all_actions = [ q[o] for o in q if o.startswith('action') and not (hasattr(q[o], "scheduled") or hasattr(q[o], "completed"))]
                # available_robots = [ r for r in central_node.robots if r.current_task == None ]

                # for act in all_actions:

                #     ### Scheduling Policy and Path 

                #     # Scheduling - if we can schedule a task, try and schedule it 
                #     cur_action = act
                #     target_robot = central_node.schedule_task(cur_action, available_robots)
                #     robot_actor = [q[o] for o in q if o.startswith('robot')][0]

                #     target_robot.current_task = act.name
                #     cur_action.scheduled = True 

                #     print("SCHEDULED", act.name)
                #     scheduled_tasks[act.name] = {
                #         'action' : cur_action,
                #         'robot' : target_robot,
                #         'robot_actor' : robot_actor
                #     }
                # for i in range(len(robots)):
                #     if len(central_node.vg.smt_solution[i]):
                #         current_instruction = central_node.vg.smt_solution[i][0]

                #         print(type(robots[0]), type(central_node.robots[0]))
                #         move_robot = central_node.find_robot_by_name()
                #         central_node.send_instruction(move_robot, current_instruction)

                for name in central_node.vg.smt_dict:
                    rob = central_node.vg.smt_dict[name]
                    sol = rob['solution']

                    if len(sol):
                        move_robot = central_node.find_robot_by_name(rob['name'])[0]
                        central_node.send_instruction(move_robot, sol[0])
                        sol.pop(0)
                # ### Stage 3 -> Path Planning
                # for act in scheduled_tasks:

                #     # Tasks 
                #     task = scheduled_tasks[act]
                    
                #     print(task)

                #     # Move the robot forward
                #     target_robot = task['robot']
                #     target_robot.move(1)
                
                # ### Stage 4 -> Task Completion
                # new_scheduled_tasks = {}
                # for act in scheduled_tasks: 
                #     task = scheduled_tasks[act]

                    
                #     action = task['action']
                #     target_robot = task['robot']
                #     robot_actor = task['robot_actor']

                #     if action.intersects_with(robot_actor.bbox):
                #         # Mark action as completed 
                #         print("Completed action", action.name)
                #         target_robot.current_task = None
                #         action.completed = True
                    
                #     else:
                #         new_scheduled_tasks[act] = {
                #             "action" : action,
                #             "robot" : target_robot,
                #             "robot_actor" : robot_actor
                #         }
                
                # scheduled_tasks = new_scheduled_tasks

                # print('Identified actions', all_actions)

                # if pos1 is not None and pos2 is not None:     
                #     instructions = [(uf.ROBOT_ONE, (float(pos1[0]), float(pos1[1]))), (uf.ROBOT_TWO, (float(pos2[0]), float(pos2[1])))]
                central_node.vg.display_robot_instructions(frame, instructions)
                cv.imshow(f'video feed: {video_input}', frame)
            if cv.waitKey(1) == ord('q') or central_node.vg.running == False:
                break
            if time.time() - last_time > 2:  
                last_time = time.time()
                # if not solver_ran:
                #     solution = central_node.run_solver(robots)
                #     solver_ran = True
                #     schedules = central_node.convert_solution_to_schedules(solution)
                #     instructions = central_node.generate_point_to_point_movement_instructions(schedules)
                #     print("Instructions: ", instructions)
                #     # central_node.send_instructions(instructions)

            if cv.waitKey(1) == ord('t'):
                central_node.vg.deadline_threshold = (central_node.vg.deadline_threshold % 2000) - 100 
                for qr_code in central_node.vg.tracked_qr_objects.keys():
                    action_point_node = central_node.vg.get_nearest_node_to_actionpoint(qr_code)
                    if action_point_node:
                        print(f"Action point {qr_code}: {action_point_node}")

            if cv.waitKey(1) == ord('g'):
                central_node.vg.display_grid = not central_node.vg.display_grid

            if cv.waitKey(1) == ord('o'):
                central_node.vg.display_obstacles = not central_node.vg.display_obstacles
            
            if cv.waitKey(1) == ord('p'):
                central_node.vg.display_paths = not central_node.vg.display_paths

            if cv.waitKey(1) == ord('h'):
                central_node.vg.display_HUD = not central_node.vg.display_HUD

    finally:
        central_node.tear_down()
        print("Final block finished")
    
class CentralNode:

    CORNER_OFFSET_CM = 0.5 # offset from the corner to the edge of our rectangle
    HEIGHT_CM = 61.5 - 2*CORNER_OFFSET_CM  
    LENGTH_CM = 92 - 2*CORNER_OFFSET_CM
    def __init__(self, camera_input, robots):
        self.vg = v2g.VideoToGraph(CentralNode.HEIGHT_CM, CentralNode.LENGTH_CM, camera_input, robots)
        self.robot_data = robots
        self.camera_input = camera_input
        self.has_already_calibrated = False
        self.robots = []

    def init(self):
        # TEMPORARY, REMOVE LATER
        # self.robots = self.init_robots(self.robot_data) # ensure connection is established
        pass 

    def find_robot_by_name(self, name):
        return [r for r in self.robots if r.device_name == name]

    def tracking_robot(self, name):
        return any([r.device_name == name for r in self.robots])
    
    def schedule_task(self, action, available_robots):
        return available_robots[0]

    def can_calibrate(self):
        if self.has_already_calibrated:
            return False 
        
        for rob in self.robots:
            if rob.device_name not in self.vg.tracked_qr_objects:
                print("CANT CALIBRATE!!! DIDNT FIND", rob.device_name)
                return False
        
        if not self.has_already_calibrated:
            self.has_already_calibrated = True
            return True 

        return False
            
        

    def calibrate(self):
        print("CALIBRATING!!!")
        self.robot_calibration_and_sync()


    def init_robots(self, robots, reconnect_time = 2):
        all_robots = []
        for r in robots:
            new_robot = IndividualNode(
                r["address"],
                r['name'],
                r['write_uuid'],
                reconnect_time
            ) 

            new_robot.init()

            # Mark the robot as available for the task
            new_robot.current_task = None


            all_robots.append(new_robot)


        self.robots.extend(all_robots)
        return all_robots

    def init_bluetooth_module(self):
        pass

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
            
            for step in schedule:
                task_str = f"Task {step['task_id']}" if step['task_id'] is not None else "N/A"
                print(f"{step['time']} | {step['location']} | {step['action']} | {task_str}") 
        return robot_schedules


    def send_instructions(self, robot, instructions):
        for instruction in instructions:
            self.send_instruction(robot, instruction)
        pass

    def send_instruction(self, robot, instruction, duration=None):
        if instruction.startswith('F'):
            robot.move(1)
        elif instruction.startswith('L'):
            robot.turn(-90)
        elif instruction.startswith('R'):
            robot.turn(-90)
        # elif instruction == 'P' or  instruction == 'D':
        #     self.motor_controller.spin()
        print(f"sent to robot: {robot}, instruction: {instruction}")
        return

    def robot_calibration_and_sync(self, robots, eps = 1e-3):
        # ensure that movement is calibrated
        # move forward, orientation etc
        for robot in robots:
            print("Calibrating", robot.device_name)
            
            # Move the robot forward 1 
            initial_pos = self.vg.get_robot_positions(robot.device_name)
            robot.move(1)
            final_pos = self.vg.get_robot_positions(robot.device_name)

            print("DOOONE")

            print("Initial and final pos", initial_pos, final_pos)

    def tear_down(self):
        # Stop the thread and release resources 
        self.vg.tear_down()
        if self.vg.thread.is_alive():
            print(f"Thread {self.vg.thread.getName()} is alive: {self.vg.thread.is_alive()}")
            self.vg.thread.join()
        print("Tear down done")

if __name__ == "__main__":
    # cap = cv.VideoCapture(0)
    main()