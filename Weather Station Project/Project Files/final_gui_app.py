import struct
import sys
import serial
from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFrame, QMessageBox
from PyQt5.QtChart import QChart, QChartView, QLineSeries, QDateTimeAxis, QValueAxis
from PyQt5.QtGui import QPainter
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class MyApp(QWidget):
    def __init__(self):
        super().__init__()

        # serial port values for UART comminication
        self.port_name = 'COM5'
        self.baud_rate = 115000

        # Devices and service mappings with custom protocol ids
        self.devices = ['i2c sensor', 'BLE sensor']
        self.device_mappings = {'i2c sensor': 0x01, 'BLE sensor': 0x02}
        self.device_type_mappings = {'i2c sensor': 0x01, 'BLE sensor': 0x02}
        self.operation_mapping = {'read': 0x01, 'write': 0x02, 'registry': 0x03}
        self.service_mappings = {'HTP guages': 0x01, 'Humidity Aggregation': 0x02, 'Pressure Aggregation': 0x03,
                                 'Temperature Aggregation': 0x04, 'Time Series': 0x05}
        # Devices list
        self.devices = ['i2c sensor', 'BLE sensor']

        # services for each device
        self.device_services = {
            'i2c sensor': ['Humidity Aggregation', 'Pressure Aggregation', 'Temperature Aggregation', 'Time Series'],
            'BLE sensor': ['Humidity Aggregation', 'Pressure Aggregation', 'Temperature Aggregation', 'Time Series']
        }

        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("background-color: black; color: white;")

        layout = QVBoxLayout(self)

        # Device buttons
        self.devices_layout = QHBoxLayout()
        self.devices_layout.setAlignment(Qt.AlignTop)

        for device_name in self.devices:
            device_button = QPushButton(device_name, self)
            device_button.setStyleSheet("background-color: lightgrey; color: black;")
            device_button.clicked.connect(lambda _, device=device_name: self.show_services(device))
            self.devices_layout.addWidget(device_button)

        layout.addLayout(self.devices_layout)

        # Layout for services
        self.services_layout = QHBoxLayout()
        self.services_layout.setAlignment(Qt.AlignTop)

        layout.addLayout(self.services_layout)

        # internal services frame
        self.services_frame = QFrame()
        self.services_frame.setStyleSheet("background-color: black; color: white; border: 2px solid lightgrey;")
        self.services_frame_layout = QVBoxLayout(self.services_frame)

        layout.addWidget(self.services_frame, stretch=1)

        self.setLayout(layout)
        self.setGeometry(100, 100, 800, 600)
        self.setWindowTitle('Pico Data Reader')

        self.show()

    def show_services(self, selected_device):
        # Clear existing service buttons
        for i in reversed(range(self.services_layout.count())):
            self.services_layout.itemAt(i).widget().setParent(None)

        # Get services for the selected device from the device-services dictionary
        services_for_device = self.device_services.get(selected_device, [])

        for service_name in services_for_device:
            service_button = QPushButton(service_name, self)
            service_button.setStyleSheet("background-color: lightgrey; color: black;")
            service_button.clicked.connect(lambda _, service=service_name: self.show_service_data(selected_device, service))
            self.services_layout.addWidget(service_button)




    def show_service_data(self, device, service):
        serial_port = serial.Serial(self.port_name, self.baud_rate)
        #conditionals for selected services
        if service == 'Time Series':
            try:
                self.send_request(serial_port, device, service, "read", None)
                htp_arr = self.receive_response(serial_port)
                self.show_time_series_chart(htp_arr)
            except Exception as e:
                self.show_error_message(str(e))
            finally:
                serial_port.close()
        elif service in ['Humidity Aggregation', 'Pressure Aggregation', 'Temperature Aggregation']:

            try:
                self.send_request(serial_port, device, service, "read", None)
                aggr_arr = self.receive_response(serial_port)
                print("aggr",aggr_arr)
                print("service",service)
                self.show_bar_graph(service,aggr_arr)
            except Exception as e:
                self.show_error_message(str(e))
            finally:
                serial_port.close()
        else:
            # Other services can be added further
            print("place holder")

    def show_time_series_chart(self, htp_arr):
        chart = QChart()
        chart.setTitle('Time Series Chart')


        humidity_values = list(map(lambda x: x / 100.0, htp_arr[:10]))
        temperature_values = list(map(lambda x: x / 100.0, htp_arr[10:20]))
        pressure_values = list(map(lambda x: x / 10.0, htp_arr[20:]))

        data = {'Humidity': humidity_values, 'Temperature': temperature_values, 'Pressure': pressure_values}

        for variable, values in data.items():
            series = QLineSeries()
            series.setName(variable)

            for i, value in enumerate(values):
                series.append(i * 10000, value)

            chart.addSeries(series)

            axis_y = QValueAxis()
            axis_y.setTitleText(variable)

            # Setting individual ranges for each Y-axis
            if variable == 'Humidity':
                axis_y.setRange(0, 100)
            elif variable == 'Temperature':
                axis_y.setRange(0, 30)
            elif variable == 'Pressure':
                axis_y.setRange(800, 1200)

            chart.addAxis(axis_y, Qt.AlignLeft)
            series.attachAxis(axis_y)

        axis_x = QDateTimeAxis()
        axis_x.setFormat('mm:ss')
        axis_x.setTickCount(10)  #  number of ticks as needed
        chart.addAxis(axis_x, Qt.AlignBottom)

        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.Antialiasing)

        # Clear existing content in the service frame layout
        for i in reversed(range(self.services_frame_layout.count())):
            self.services_frame_layout.itemAt(i).widget().setParent(None)

        # Adding the chart view to the service frame
        self.services_frame_layout.addWidget(chart_view)

    def show_bar_graph(self, aggregation_type,aggregation_arr):

        categories = ['Avg', 'Min', 'Max']
        values = [x / 100.0 for x in aggregation_arr]  # to get the float value
         #setting the units and data format based on the service selected
        if aggregation_type == 'Humidity Aggregation':
            unit = '%'
            print("hum agg:" , values)
        elif aggregation_type == 'Pressure Aggregation':
            values= [x / 10.0 for x in aggregation_arr]
            unit = 'hPa'
            print("pres agg:" , values)
        elif aggregation_type == 'Temperature Aggregation':
            print ("temp agg:",values)

            unit = '°C'
        else:
            values = []
            unit = ''

        # Create bar graph using Matplotlib
        fig, ax = plt.subplots()
        ax.bar(categories, values, color=['blue', 'green', 'red'])
        ax.set_ylabel(f'{aggregation_type} ({unit})')
        ax.set_title(f'{aggregation_type} Bar Graph')

        # Display Matplotlib plot in a PyQt window
        mpl_canvas = FigureCanvas(fig)
        mpl_canvas.setGeometry(0, 0, 400, 300)  # Adjust the size as needed

        # Clear existing content in the service frame layout
        for i in reversed(range(self.services_frame_layout.count())):
            self.services_frame_layout.itemAt(i).widget().setParent(None)

        # Add the Matplotlib canvas to the service frame
        self.services_frame_layout.addWidget(mpl_canvas)

    def send_request(self, serial_port, device, command, operation, params_arr):
        #custom protocol request dataframe construction
        protocol_id = 0x01
        channel_id = 0x01
        device_id = self.device_mappings[device]
        device_type_id = self.device_type_mappings[device]
        operation_id = self.operation_mapping[operation]
        command_id = self.service_mappings[command]

        nparams = len(params_arr) if params_arr is not None else 0

        header_bytes = bytes([protocol_id, channel_id, device_id, device_type_id, operation_id])
        command = header_bytes + struct.pack("<h", command_id) + bytes([nparams])
        #sending the custom request dataframe over serial port
        serial_port.write(command + b'\n')

    def receive_response(self, serial_port):
        #deconstructing the custom protocol dataframe recieved over serial-uart interface
        response_command = serial_port.readline()[:-1]
        protocol_id = response_command[0]
        channel_id = response_command[1]
        device_id = response_command[2]
        device_type_id = response_command[3]
        operation_id = response_command[4]
        command = struct.unpack("<h", response_command[5:7])[0]
        print(command)
        nresults = response_command[7]
        unit_id = response_command[8]  # datatype
        # 0x02 for array type, set the timeserinit id accordingly in central pico

        #conditionals for the data type recieved and the command type
        if unit_id == 0x02 and command==0x05:
            result = []
            print(response_command)

            print("nresults", nresults)
            result = struct.unpack("<30H", response_command[9:9 + 2 * nresults])
            #result=[x / 100.0 for x in result]
            print("result_arr:", result)
        elif  command in (0x04,0x03,0x02) :
            print(response_command[9:])
            result = struct.unpack("<3H", response_command[9:9 + 2 * nresults])
            print("aggr_arr",result)
        else:
            result = struct.unpack("<h", response_command[9:11])[0]
            print("entered else")
        return result

#method for popping up a small error window in case of exceptions or other error ids passed in dataframe
    def show_error_message(self, message):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setText("Error")
        msg_box.setInformativeText(message)
        msg_box.exec_()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MyApp()
    sys.exit(app.exec_())
