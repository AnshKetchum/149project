import json 
import time 
import os 
from dotenv import load_dotenv

import cv2 as cv
from central.central import CentralNode
from utils import UtilityFunctions
from solver.video_graph import VideoToGraph


DIAGONAL_MULTIPLIER = 1.414
uf = UtilityFunctions()

def main():
    e = os.getenv("VIDEO_FEED")

    print("Video feed", e)
    cap = cv.VideoCapture(e)
    time.sleep(5)

    # video_graph = VideoToGraph(100, 100, os.getenv("VIDEO_FEED"), [], thread=False)
    # video_graph.initialize_camera()
    actors = []
    while not actors:
        actors = uf.get_all_objects(cap)

    print([a.name for a in actors])


if __name__ == '__main__':
    load_dotenv()

    print("Running main ...")
    main()
    