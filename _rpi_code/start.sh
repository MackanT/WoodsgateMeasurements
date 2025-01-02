#!/bin/bash
echo "Running Daily Reset..."
sudo pkill -F /home/admin/Documents/5400.pid
sudo python /home/admin/Documents/woodsgate_5400.py &
echo $! > /home/admin/Documents/5400.pid
