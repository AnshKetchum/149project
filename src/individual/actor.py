import json
from central.vision import Actor, ActorType
from apis.bluetooth import BluetoothAPI
from individual.client import RobotPhysicalInterface


class IndividualNode(Actor):
    TYPE = ActorType.ROBOT

    def can_connect(name):
        data = BluetoothAPI.get_device_data(name)
        if data is None:
            return False 
        return BluetoothAPI.can_connect(data['address'], data['write_uuid'])

    def __init__(self, name):
        super().__init__(name)

        # Connect to the physical bluetooth device
        device_data = BluetoothAPI.get_device_data(name)
        physical_interface = RobotPhysicalInterface(device_data['address'], device_data['name'], device_data['write_uuid'])

        # Set the physical interface
        self.set_physical_interface(physical_interface)




