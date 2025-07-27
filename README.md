# WoodsgateMeasurements
Measurement sw for a Rosemount 5300 probe in a water tank using a RPI with MCP3008 ADC measuring mA over GPIO

Actual Measurement Setup
![IMG_20230714_162212](https://github.com/user-attachments/assets/19feca03-0a48-449b-9eea-175432623040)

Indoor Wiring (Cables running underground from pump to biuilding) 
-ADC converter
![IMG_20230714_084652](https://github.com/user-attachments/assets/bd53519a-2ea2-48a6-95b9-3e02ef64b8d2)
-RPI connection
![IMG_20230714_084659](https://github.com/user-attachments/assets/3243b284-c612-42c8-829f-b3a5cebb1e7f)


### Setup Keyless-SSH
- Generate a ssh-pair on your local pc: ´ssh-keygen -t ed25519 -C "your_email@example.com"´
- Copy over keygen to rpi: ´cat ~/.ssh/id_ed25519.pub | ssh -p 22 admin@192.168.1.74 "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"´ **NOTE**: if using remote network, change 192.168.1.74 to tailscale IP
- Upon running above command you will be promtped one last time to enter the password to the RPI, afterwards you can access the rpi without password

