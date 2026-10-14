# harvest-usb-collection

### Overview
Find the MeterDataTest folder in the harvest computer's Documents folder.

Usage:
    python find_meter_data.py C:/Users/[Username]/   # all user profiles on a local machine

The script looks in each user's Documents folder (including the OneDrive-redirected
Documents folder) and searches up to --depth levels below it for MeterDataTest.

Inside MeterDataTest it looks through each subfolder and copies the CSV files
(named YYYY-MM-DD_<meter>.csv) dated on or after the date in track_date.csv into
a NewData folder in the same Documents folder, keeping the meter subfolders.
Files already in NewData that are unchanged (same size and modified time) are skipped;
a file that has grown since the last run is copied again. After a run with no copy
failures, track_date.csv is updated to the newest file date copied, and the next run
starts from that same date. Use --dest to copy elsewhere.

### How to run script
- move "find_meter_data.py" and track_date.csv to the Downloads folder on the computer that has the harvest data on it
- find the Downloads folder with the script
    - go to file explorer and click on This PC -> OS (C:) -> Users -> (not public) -> Downloads
    - click on the address bar and copy the path (e.g. C:\Users\[Username]\Downloads)
- go to search bar at the bottom and type powershell and click on Windows Powershell
- paste in the copied file address and hit enter:
    cd "C:\Users\[Username]\Downloads"
- take the previous address, remove Downloads and paste it at the end of the command below and hit enter:
    python3 find_meter_data.py C:/Users/[Username]/
- then open file explorer and go to the Documents folder and you should see a NewData folder 
  with the copied files that you should then move the usb drive stick