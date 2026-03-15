#!/bin/bash

INTERFACE="wlan1"
CHANNEL="6"

echo "Taking $INTERFACE down..."
sudo ip link set $INTERFACE down

echo "Setting $INTERFACE to monitor mode..."
sudo iw dev $INTERFACE set type monitor

echo "Bringing $INTERFACE back up..."
sudo ip link set $INTERFACE up

echo "Locking $INTERFACE to channel $CHANNEL..."
sudo iw dev $INTERFACE set channel $CHANNEL

echo "Configuration complete. Verifying:"
iwconfig $INTERFACE
