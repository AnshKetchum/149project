import json 
import os
from dotenv import load_dotenv

from apis.bluetooth import BluetoothAPI
from individual.client import RobotPhysicalInterface

if __name__ == "__main__":
    load_dotenv()
    BluetoothAPI.refresh()

    with open('devices.json', 'r') as f:
        dct = json.load(f)
    
    d = dct["devices"][0]

    if os.getenv('SOLE_ROBOT_NAME', None):
        d = [d for d in dct["devices"] if d["name"] == os.getenv('SOLE_ROBOT_NAME', None)][0]

    robot = RobotPhysicalInterface(device_address=d['address'], device_name=d['name'], characteristic_uuid=d['write_uuid'])

    # Register and connect the robot
    print(robot.add_robot())
    print(robot.connect())

    # Get angle data
    print(robot.get_angle_data())

    # Move the robot
    print(robot.move(0.25))

    # Get distance data
    print(robot.get_distance_data())

    # Disconnect from the robot
    print(robot.disconnect())

    BluetoothAPI.refresh()