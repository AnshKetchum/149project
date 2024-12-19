import json 
import time 
import os 
from dotenv import load_dotenv

import cv2 as cv
from apis.bluetooth import BluetoothAPI
from central.central import CentralNode
from utils import UtilityFunctions
from solver.video_graph import VideoToGraph
from central.vision import Actor, ActorType

uf = UtilityFunctions()

def main():
    # Refresh our bluetooth serverIn
    BluetoothAPI.refresh()

    # Setup the camera 
    e = int(os.getenv("VIDEO_FEED"))
    cap = VideoToGraph.initialize_camera(e)
    print("Video feed", e)

    # Define the central node 
    central_node = CentralNode(e, [], True)

    # Stall while the video graph doesn't have data on the tracked objects
    while not central_node.vg.completed_initial_smt():
        time.sleep(1)

    # Silly test for sanity
    for k in central_node.vg.tracked_robots:
        actor = central_node.vg.tracked_robots[k]

        if actor.TYPE == ActorType.ROBOT:
            print('Found a robot', actor.name)
            central_node.calibrate_robot(actor)

    # Refresh our bluetooth server 
    BluetoothAPI.refresh()


if __name__ == '__main__':
    load_dotenv()

    print("Running main ...")
    main()
    