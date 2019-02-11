## Configuration

When you start Holidays Google node server for the first time, it will use your browser to authenticate your Google account. Complete this process for Holidays Google node server to function.

Holidays Google node server accepts a list of calendars in your account to check for holidays. It will poll holidays changes every long poll (default is 60 seconds). In order for event to be considered as a holiday, it needs to be *full day event* AND it needs to *show time as free*.

Two nodes will be created for each configured calendar - today and tomorrow.

**DO NOT CHANGE RELATIVE ORDER OF CONFIGURED CALENDAR NAMES.** Doing this will change underlying ISY nodes to the new configuration, potentially requiring you to change ISY programs.
