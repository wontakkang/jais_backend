# DJANGO
python manage.py makemigrations
python manage.py migrate
python manage.py 192.168.0.63:8000

# FAST API
uvicorn main:app --reload --host 192.168.0.159 --port 8000 -- reload

# gunicorn
# 1. 기존 서비스 중지 (필요시)
sudo systemctl stop gunicorn
sudo systemctl stop nginx
# 2. 서비스 파일 복사
sudo cp /home/sysnet/projects/deployment/gunicorn.service /etc/systemd/system/

# 3. 시스템 데몬 재로드
sudo systemctl daemon-reload

# 4. 통합 서비스 시작 및 활성화
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
sudo systemctl restart gunicorn

# 5. nginx 설정 적용 (필요시)
sudo cp /home/sysnet/projects/deployment/nginx.conf /etc/nginx/sites-available/default
sudo systemctl restart nginx

# 6. 서비스 상태 확인
sudo systemctl status gunicorn
sudo systemctl status nginx

# uvicorn (main.py) 사용자 서비스 설치/재시작 및 확인
# 1) 사용자 단위 서비스 설치 경로에 유닛 배치 (sudo 불필요)
mkdir -p ~/.config/systemd/user
cp /home/sysnet/projects/deployment/uvicorn.service ~/.config/systemd/user/
# 2) 사용자 데몬 재로드 및 즉시 활성화/시작
systemctl --user daemon-reload
systemctl --user enable --now uvicorn
# 3) 서비스 재시작
systemctl --user restart uvicorn
# 4) 서비스 상태 확인
systemctl --user status uvicorn
# 5) 실시간 로그 확인(종료: Ctrl+C)
journalctl --user -u uvicorn -f
# 6) 최근 로그 확인
journalctl --user -u uvicorn -n 200 --no-pager
# 7) 로그아웃 이후에도 자동 시작하려면(선택): 관리자가 유저 linger 활성화
#    sudo loginctl enable-linger <username>

