import requests
from dotenv import load_dotenv
import json 
import os

from apis.bluetooth import BluetoothAPI

class RobotPhysicalInterface(BluetoothAPI):
    def __init__(self, device_address: str, device_name: str, characteristic_uuid: str, reconnect_time = 2, api_url: str = "http://127.0.0.1:8000"):
        super().__init__(device_address, device_name, characteristic_uuid, reconnect_time, api_url)

        self.calibration = 1

    def init(self):
        """Asynchronous initialization."""
        print("Init")
        self.disconnect()
        print("Disconnected")
        r = self.add_robot()
        print("add_robot", r)
        r = self.connect()
        print("connect", r)
        self.reset_angle_data()
        self.reset_distance_data()
        print("Init complete")

    def set_calibration(self, calibration_factor):
        self.calibration = calibration_factor

    def add_robot(self):
        """Register a robot with the server."""
        response = requests.post(f"{self.api_url}/add_robot", json={
                "device_address": self.device_address,
                "characteristic_uuid": self.characteristic_uuid,
        })
        return response.json()

    def get_angle_data(self):
        """Get angle data from the robot."""
        return self.send_command("ANGLE+0", need_data=True)

    def get_distance_data(self):
        """Get distance data from the robot."""
        return self.send_command("ENCODER+2", need_data=True)

    def move(self, distance: float):
        """Send a move command."""
        print("MOOOOOOOOOVING")
        fdist = distance * self.calibration
        return self.send_command(f"MOVE+{fdist:.4f}")

    def turn(self, angle_in_degrees: float):
        """Send a turn command."""
        return self.send_command(f"TURN+{angle_in_degrees}")

    def reset_angle_data(self):
        command = f"ANGLE+1"
        return self.send_command(command, need_data=False)
    
    def reset_distance_data(self):
        """Reset distance data."""
        return self.send_command("ENCODER+3")

