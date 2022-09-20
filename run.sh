#!/usr/bin/env bash

aws s3 cp s3://cnu-2k17/cd/security_secrets.yaml .

if [ "$RAILS_ENV" = "Dev" ];
then
	aws s3 cp s3://cnu-2k17/cd/ad_dev_config.py ad_service/utils/config.py
fi
apache2ctl -D FOREGROUND