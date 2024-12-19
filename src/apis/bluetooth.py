import requests
import json

class BluetoothAPI:
    API_URL = "http://127.0.0.1:8000"
    def __init__(self, device_address: str, device_name: str, characteristic_uuid: str, reconnect_time = 2, api_url: str = "http://127.0.0.1:8000"):
        self.device_address = device_address
        self.device_name = device_name
        self.name = device_name
        self.characteristic_uuid = characteristic_uuid
        self.api_url = api_url

        self.device_data_json = {
            "device_address" : self.device_address, 
            "characteristic_uuid" : self.characteristic_uuid
        }
    
    def refresh():
        response = requests.post(f"{BluetoothAPI.API_URL}/refresh")

        r = response.json()
        return r

    def get_device_data(name):
        data = None 

        with open('devices.json', 'r') as f:
            dct = json.load(f)
            for d in dct['devices']:
                if d['name'] == name:
                    data = d
                    break 

        return data

    
    def can_connect(device_address, characteristic_uuid):
        """Synchronous wrapper for the can connect API."""
        response = requests.post(f"{BluetoothAPI.API_URL}/can_connect", json={
                "device_address": device_address,
                "characteristic_uuid": characteristic_uuid,
        })

        r =  response.json()
        print("Got CAN_CONNECT response ", r)
        return r['status'] == 'can_connect'

    def connect(self):
        """Synchronous wrapper for the connect API."""
        response = requests.post(f"{self.api_url}/connect", json={
                "device_address": self.device_address,
                "characteristic_uuid": self.characteristic_uuid,
        })
        return response.json()

    def disconnect(self):
        """Synchronous wrapper for the disconnect API."""
        response = requests.post(f"{self.api_url}/disconnect", json={
                "device_address": self.device_address,
                "characteristic_uuid": self.characteristic_uuid,
        })
        return response.json()

    def send_command(self, command: str, need_data: bool = False):
        """Synchronous wrapper for sending commands."""
        c = self.connect()
        print("CONNECTION", c)

        data = {"command": command, "need_data": need_data}
        response = requests.post(f"{self.api_url}/send_command", json={
            "robot_connection" : {
                "device_address": self.device_address,
                "characteristic_uuid": self.characteristic_uuid,
            },
            "command" : data
        })
        

        return response.json()
