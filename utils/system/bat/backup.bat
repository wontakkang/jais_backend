set CUR_DATE=%date:~0,4%-%date:~5,2%-%date:~8,2%
echo %CUR_DATE%
%1 -h localhost -u root -pdaeeun12345 --all-databases > %2\dbbackup-%CUR_DATE%.sql