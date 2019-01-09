# QualysRequester

QualysRequester is used to download reports from Qualys via their API by report name. This script allows for the user to pass arguments by setting flags and specifying a file path for their download(s). 

## Options

To specify the report or reports the user must enter a full name or partial name in the config file. The user should only specify one and leave the other option blank. 

--help : Simple help menu <br/>
-o : Specify the file path for the output. At the moment the absolute path must be used. 

If there is any feedback or suggestions please feel free to reach out to me or the original author [@fragtastic]( https://github.com/fragtastic ). He has been fantastic in helping me on my journey in learning Python. 

## Example Uses

MacOS / Linux . 
username$ python3 app.py -0 /Users/{username}/Desktop/QualysReports
