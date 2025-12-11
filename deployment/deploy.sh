#!/bin/bash

# Deployment Script for Autosetup on AWS Ubuntu

echo "Starting Deployment..."

# 1. System Updates
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv nginx git

# 2. Setup Project Directory (Assuming we are inside the repo)
# If this is a fresh clone, we'd clone here. For now, assuming current dir.
cd /home/ubuntu/geospatial-tagging-thesis

# 3. Python Environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install flask flask-sqlalchemy flask-login gunicorn

# 4. Initialize Database & Admin (One off)
# export FLASK_APP=web_app/app.py
# flask create-admin

# 5. Configure Nginx
sudo cp deployment/nginx_site.conf /etc/nginx/sites-available/geospatial
sudo ln -sf /etc/nginx/sites-available/geospatial /etc/nginx/sites-enabled
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

# 6. Create Systemd Service for Gunicorn
sudo bash -c 'cat > /etc/systemd/system/geospatial.service << EOL
[Unit]
Description=Gunicorn instance to serve geospatial app
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/geospatial-tagging-thesis/web_app
Environment="PATH=/home/ubuntu/geospatial-tagging-thesis/venv/bin"
ExecStart=/home/ubuntu/geospatial-tagging-thesis/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 app:app

[Install]
WantedBy=multi-user.target
EOL'

# 7. Start Service
sudo systemctl daemon-reload
sudo systemctl start geospatial
sudo systemctl enable geospatial

echo "Deployment Complete! Visit http://osm.texodus.tech"
echo "Don't forget to run 'flask create-admin' manually if you haven't already!"
