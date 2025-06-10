import tkinter as tk
from tkinter import ttk
import threading
import time
import struct
import csv
import random
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mc_api import *


class EscConnectivity:
    def __init__(self):
        self.current_speed = 0
        self.uart = UART()

    def set_speed(self, speed_rpm: int):
        self.uart.send_mc_packet(McPacket.set_speed_rpm(speed_rpm))
        self.current_speed = speed_rpm

    def read_telemetry(self):
        mc_packet = self.uart.send_mc_packet(McPacket.telemetry_request())
        print(mc_packet)
        if not mc_packet:
            return 0, 0, 0, 0, 0
        return mc_packet.duty_cycle, mc_packet.reference_speed, mc_packet.average_speed, mc_packet.motor_state, mc_packet.crc


class MotorGUI:
    def __init__(self, root):
        self.master = root
        self.comm = EscConnectivity()
        self.target_speed = tk.IntVar(value=0)
        self.motor_state_text = tk.StringVar(value="Unknown")
        self.motor_state_label = tk.Label(self.master, textvariable=self.motor_state_text, font=('TkDefaultFont', 12, 'bold'))
        self.motor_state_label.pack()

        self.running = True

        # Logging
        self.telemetry_log = open('telemetry_log.csv', 'w', newline='')
        self.oscillation_log = open('oscillation_log.csv', 'w', newline='')
        self.telemetry_writer = csv.writer(self.telemetry_log)
        self.oscillation_writer = csv.writer(self.oscillation_log)
        self.telemetry_writer.writerow(['Time', 'DutyCycle', 'ReferenceSpeed', 'AverageSpeed', 'MotorState'])
        self.oscillation_writer.writerow(['Time', 'Oscillation (%) (avg)', 'Oscillation (%) (ref)'])

        self.speed_history = []

        self.setup_gui(root)
        threading.Thread(target=self.update_telemetry_loop, daemon=True).start()

    def setup_gui(self, root):
        frame = ttk.Frame(root)
        frame.pack(padx=10, pady=10)

        ttk.Label(frame, text="Target Speed (RPM):").grid(row=0, column=0)
        entry = ttk.Entry(frame, textvariable=self.target_speed)
        entry.grid(row=0, column=1)

        self.slider = ttk.Scale(frame, from_=0, to=10000, orient='horizontal', command=self.slider_changed)
        self.slider.grid(row=1, column=0, columnspan=2, sticky='ew')

        set_btn = ttk.Button(frame, text="Set Speed", command=self.set_speed)
        set_btn.grid(row=2, column=0)

        test_btn = ttk.Button(frame, text="Start Test", command=self.start_test)
        test_btn.grid(row=2, column=1)

        ttk.Label(frame, text="Motor State:").grid(row=3, column=0)
        ttk.Label(frame, textvariable=self.motor_state_text, foreground="blue").grid(row=3, column=1)

        self.fig, self.ax = plt.subplots(3, 1, figsize=(7, 6), tight_layout=True)
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.time_data = []
        self.ref_speed_data = []
        self.avg_speed_data = []
        self.duty_data = []
        self.state_data = []

    def update_motor_state_display(self, state_code):
        state_name = self.get_state_name(state_code)
        self.motor_state_text.set(state_name)

        # Decide color
        if state_name == "RUN":
            color = "green"
        elif state_name in ("ALIGNMENT", "START", "SWITCH_OVER", "CHARGE_BOOT_CAP", "OFFSET_CALIB"):
            color = "orange"
        elif state_name in ("FAULT_NOW", "FAULT_OVER", "STOP", "WAIT_STOP_MOTOR", "ICLWAIT"):
            color = "red"
        elif state_name == "IDLE":
            color = "gray"
        else:
            color = "black"

        self.motor_state_label.config(fg=color)


    def slider_changed(self, val):
        self.target_speed.set(int(float(val)))

    def set_speed(self):
        speed = self.target_speed.get()
        self.comm.set_speed(speed)

    def update_telemetry_loop(self):
        while self.running:
            telemetry = self.comm.read_telemetry()
            if telemetry:
                duty, ref, avg, state, crc = telemetry
                now = time.time()
                self.time_data.append(now)
                self.duty_data.append(duty)
                self.ref_speed_data.append(ref)
                self.avg_speed_data.append(avg)
                self.state_data.append(state)
                self.speed_history.append(avg)
                if len(self.speed_history) > 50:
                    self.speed_history.pop(0)

                self.update_motor_state_display(state)
                
                state_str = self.get_state_name(state) 

                self.telemetry_writer.writerow([now, duty, ref, avg, state_str])
                self.telemetry_log.flush() 
                self.check_oscillations(now, avg, ref)
                self.update_plots()


            time.sleep(0.5)

    def update_plots(self):
        for a in self.ax: a.clear()
        self.ax[0].plot(self.time_data[-100:], self.duty_data[-100:], label='DutyCycle')
        self.ax[1].plot(self.time_data[-100:], self.ref_speed_data[-100:], label='ReferenceSpeed', color='orange')
        self.ax[2].plot(self.time_data[-100:], self.avg_speed_data[-100:], label='AverageSpeed', color='green')
        for a in self.ax:
            a.legend()
            a.grid(True)
        self.canvas.draw()

    STATE_MAP = {
        0: "IDLE",
        2: "ALIGNMENT",
        4: "START",
        6: "RUN",
        8: "STOP",
        10: "FAULT_NOW",
        11: "FAULT_OVER",
        12: "ICLWAIT",
        16: "CHARGE_BOOT_CAP",
        17: "OFFSET_CALIB",
        19: "SWITCH_OVER",
        20: "WAIT_STOP_MOTOR"
    }

    def get_state_name(self, state):
        return self.STATE_MAP.get(state, f"UNKNOWN ({state})")

    def check_oscillations(self, timestamp, avg_speed, ref_speed):
        if len(self.speed_history) < 10:
            return
        mean = sum(self.speed_history) / len(self.speed_history)
        max_dev = max(abs(s - mean) for s in self.speed_history)
        pct_dev_avg = (max_dev / mean) * 100 if mean > 0 else 0
        pct_dev_ref = (max_dev / ref_speed) * 100 if ref_speed > 0 else 0
        self.oscillation_writer.writerow([timestamp, f"{pct_dev_avg:.2f}", f"{pct_dev_ref:.2f}"])

    def start_test(self):
        def test_routine():
            for speed in range(4000, 8001, 1000):
                self.target_speed.set(speed)
                self.slider.set(speed)
                self.set_speed()
                time.sleep(5)
        threading.Thread(target=test_routine, daemon=True).start()

    def on_close(self):
        self.running = False
        self.telemetry_log.close()
        self.oscillation_log.close()


if __name__ == '__main__':
    root = tk.Tk()
    root.title("BLDC ESC Control Panel")
    root.geometry("900x700")
    app = MotorGUI(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.on_close(), root.destroy()))
    root.mainloop()
