from datetime import datetime

import rclpy
from rclpy.node import Node

from std_msgs.msg import String
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan

COMMAND_TOPIC_NAME = 'steering_commands'
ACTUATOR_TOPIC_NAME = '/cmd_vel'
LIDAR_TOPIC_NAME = '/scan'

DEFAULT_THROTTLE = 0.5
MAX_THROTTLE = 1.0
ZERO_THROTTLE = 0.0
MAX_LEFT_ANGLE = -1.0
MAX_RIGHT_ANGLE = 1.0
STRAIGHT_ANGLE = 0.0

MIN_ALLOWED_DISTANCE = 0.2
TIMEOUT = 10    # when to stop after receiving command (in seconds)


def get_steering_values_from_command(command: str) -> tuple[float, float, bool]:
    """Translates passed command into steering angle and throttle values.
    
    :Returns: tuple (steering_float, throttle_float, valid)
    """
    if command == "forward":
        return STRAIGHT_ANGLE, DEFAULT_THROTTLE, True
    elif command == "backward":
        return STRAIGHT_ANGLE, -DEFAULT_THROTTLE, True
    elif command == "left":
        return MAX_LEFT_ANGLE, DEFAULT_THROTTLE, True
    elif command == "right":
        return MAX_RIGHT_ANGLE, DEFAULT_THROTTLE, True
    elif command == "stop":
        return STRAIGHT_ANGLE, ZERO_THROTTLE, True
    else:
        return None, None, False


class SteeringCommandSubscriber(Node):

    def __init__(self):
        super().__init__('steering_command_subscriber')

        # Commands subscription
        self.commands_subscription = self.create_subscription(String, COMMAND_TOPIC_NAME, self.command_callback, 10)

        # LIDAR subscription
        self.lidar_subscription = self.create_subscription(LaserScan, LIDAR_TOPIC_NAME, self.lidar_callback, 10)
        
        # Publisher for actuation
        self.twist_publisher = self.create_publisher(Twist, ACTUATOR_TOPIC_NAME, 10)
        self.twist_cmd = Twist()

        # Ensure car keeps moving until receiving another command
        self.keep_moving_timer = self.create_timer(0.01, self.keep_moving)
        self.timeout = datetime.now()

    def command_callback(self, msg):
        """Move car according to incoming commands."""
        command = msg.data
        self.get_logger().info(f'Command received: "{command}". Actuating...')
        
        steering_float, throttle_float, valid = get_steering_values_from_command(command)

        if valid:
            try:
                self.timeout = datetime.now()
                self.publish_to_vesc(steering_float, throttle_float)
            except KeyboardInterrupt:
                self.stop_car()

    def stop_car(self):
        self.publish_to_vesc(STRAIGHT_ANGLE, ZERO_THROTTLE)
    
    def keep_moving(self):
        """Keep moving according to last command unless more than X seconds have passed (timeout)."""
        time_passed = (datetime.now() - self.timeout).seconds
        if time_passed <= TIMEOUT:      # Check that timeout has not lapsed
            self.twist_publisher.publish(self.twist_cmd)
        else:
            self.get_logger().info(f"Command timed out after {TIMEOUT} seconds. Stopping car...")
            self.stop_car()
        
    def lidar_callback(self, msg):
        """Listen to LIDAR signal and stop car if an obstacle gets too close."""
        ranges = msg.ranges
        start_idx = int(len(ranges) * 0.5)
        end_idx = len(ranges) - 1
        front_ranges = ranges[start_idx:end_idx]
        min_distance = min(front_ranges)

        too_close = True if min_distance <= MIN_ALLOWED_DISTANCE else False

        if too_close:
            self.get_logger().info(f'Too close ({min_distance} m). Stopping vehicle...')
            self.stop_car()

    def publish_to_vesc(self, steering_angle: float, throttle: float):
        """Publish steering angle and throttle value to VESC topic (/cmd_vel),"""
        self.twist_cmd.angular.z = steering_angle
        self.twist_cmd.linear.x = throttle
        self.twist_publisher.publish(self.twist_cmd)


def main(args=None):
    rclpy.init(args=args)

    steering_command_subscriber = SteeringCommandSubscriber()

    rclpy.spin(steering_command_subscriber)

    # Destroy the node explicitly
    # (optional - otherwise it will be done automatically
    # when the garbage collector destroys the node object)
    steering_command_subscriber.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()