import rospy

from yaw_controller import YawController
from pid import PID
from lowpass import LowPassFilter

GAS_DENSITY = 2.858
ONE_MPH = 0.44704


class Controller(object):
    def __init__(self, vehicle_mass, fuel_capacity, brake_deadband,
                 decel_limit, accel_limit, wheel_radius, wheel_base,
                 steer_ratio, max_lat_accel, max_steer_angle):
        # TODO: Implement
        min_speed = 0.1
        rospy.logwarn("max_steer_angle: {0}".format(max_steer_angle))
        rospy.logwarn("brake_deadband: {0}".format(brake_deadband))
        self.yaw_controller = YawController(wheel_base, steer_ratio, min_speed,
                                            max_lat_accel, max_steer_angle)

        kp = 0.3
        ki = 0.1
        kd = 0.
        #mn = -0.4  # Minimum throttle value
        mx = 0.4  # maximum throttle value
        mn = 0.  # Minimum throttle value
        #mx = 0.2  # maximum throttle value
        self.throttle_controller = PID(kp, ki, kd, mn, mx)

        tau = 0.5  # 1/(2pi*tau) = cutoff frequency
        ts = 0.02  # sample time
        self.vel_lpf = LowPassFilter(tau, ts)

        self.vehicle_mass = vehicle_mass
        self.fuel_capacity = fuel_capacity
        self.brake_deadband = brake_deadband
        self.decel_limit = decel_limit
        self.accel_limit = accel_limit
        self.wheel_radius = wheel_radius

        self.last_time = rospy.get_time()
        self.state = "pre-existence"
        self.state_change_time = self.last_time

    def control(self, current_vel, dbw_enabled, linear_vel, angular_vel):
        # TODO: Change the arg, kwarg list to suit your needs

        if not dbw_enabled:
            self.throttle_controller.reset()
            return 0., 0., 0.

        current_vel = self.vel_lpf.filt(current_vel)

        """
        rospy.logwarn("Angular vel: {0}".format(angular_vel))
        rospy.logwarn("Target vel: {0}".format(linear_vel))
        rospy.logwarn("Target angular vel: {0}".format(angular_vel))
        rospy.logwarn("Current vel: {0}".format(current_vel))
        rospy.logwarn("Filtered velocity vel: {0}".format(self.vel_lpf.get()))
        """

        steering = self.yaw_controller.get_steering(linear_vel,
                                                    angular_vel,
                                                    current_vel)

        vel_error = linear_vel - current_vel
        self.last_vel = current_vel

        current_time = rospy.get_time()
        sample_time = current_time - self.last_time
        self.last_time = current_time

        throttle = self.throttle_controller.step(vel_error, sample_time)
        brake = 0
        #rospy.logwarn("throttle: {:4.2},\tlinear_vel: {:.3},\tcurrent_vel: {:.3}".format(throttle, linear_vel, current_vel))

        if linear_vel == 0.0 and current_vel < 0.1:
            throttle = 0
            # N*m - to hold car in place if we are stopped at a light
            # Acceleration ~ 1m/s^2
            brake = 700
            if (self.state != "stopped"):
                rospy.logwarn("{} for {:5.2} s".format(self.state, current_time - self.state_change_time))
                self.state = "stopped"
                self.state_change_time = current_time

        elif throttle < 0.1 and vel_error < 0:  # going too fast
            decel = max(vel_error, self.decel_limit)
            # Torque N * m 
            #if throttle < 0.0:
            #    rospy.logwarn("throttle: {0}, decel: {1}, ratio: {2}".format(throttle, decel, decel/throttle))
            #decel = throttle * 5
            #decel = 0.4
            brake = abs(decel) * self.vehicle_mass * self.wheel_radius
            #rospy.logwarn("throttle: {:4.2},\tdecel: {:.3}".format(throttle, decel))
            throttle = 0
            if (self.state != "braking"):
                rospy.logwarn("{} for {:5.2} s".format(self.state, current_time - self.state_change_time))
                self.state = "braking"
                self.state_change_time = current_time
                #rospy.logwarn("{:5.2} m/s: braking".format(linear_vel))
        else:
            if (self.state != "accelerating"):
                rospy.logwarn("{} for {:5.2} s".format(self.state, current_time - self.state_change_time))
                self.state = "accelerating"
                self.state_change_time = current_time
                #rospy.logwarn("{:5.2} m/s: accelerating".format(linear_vel))

        # Return throttle, brake, steer
        return throttle, brake, steering
