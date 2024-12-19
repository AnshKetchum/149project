import numpy as np
import time
import cv2 as cv
import sys  
import os 
import json 
import requests

from solver.graph import Graph as gr
import solver.video_graph as v2g
from individual.client import Robot as IndividualNode

from central.util import UtilityFunctions as uf

DIAGONAL_MULTIPLIER = 1.414
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
        print("Sending instruction ", instruction)
        if instruction.startswith('F'):
            robot.move(int(instruction.split(':')[-1]))
        elif instruction.startswith('L'):
            robot.turn(-int(instruction.split(':')[-1]))
        elif instruction.startswith('R'):
            robot.turn(int(instruction.split(':')[-1]))
        elif instruction.startswith('P') or  instruction.startswith('D'):
            robot.turn(360)
            # self.motor_controller.spin()
        elif instruction.startswith('W'):
            pass # TO IMPLEMENT
        else:
            print("Invalid command") 

    def robot_calibration_and_sync(self, robots, eps = 1e-3):
        # ensure that movement is calibrated
        # move forward, orientation etc
        calibration = {}
        for robot in robots:
            print("Calibrating", robot.device_name)
            calibration_mapping  = self.vg.pixel_conversion.copy()
            
            # Move the robot forward 1 
            calibration = self.calibrate_robot(robot)
            robot.set_calibration(calibration)
            print("DOOONE")

    def calibrate_robot(self, robot):
        initial_pos = self.vg.get_robot_positions(robot.device_name)
        robot.move(1)
        final_pos = self.vg.get_robot_positions(robot.device_name)
        distance = gr.adjust_distance_based_on_correction_pixel(self.vg.graph, initial_pos, final_pos, self.vg.pixel_conversion)
        

        direction = gr.direction_pixel(initial_pos, final_pos, distance/3)
        if direction == gr.DIAGONAL:
            correction_factor = self.vg.block_size_cm*DIAGONAL_MULTIPLIER/distance
            calibration =  correction_factor
        else:
            correction_factor = self.vg.block_size_cm/distance
            calibration =  correction_factor

        return calibration

    def tear_down(self):
        # Stop the thread and release resources 
        self.vg.tear_down()
        if self.vg.thread.is_alive():
            print(f"Thread {self.vg.thread.getName()} is alive: {self.vg.thread.is_alive()}")
            self.vg.thread.join()
        print("Tear down done")
