#!/usr/bin/env python3

import click
import datetime
import dateutil.parser
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import pickle
import polyinterface
from polyinterface import LOGGER
import pytz


class Controller(polyinterface.Controller):

    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

    def __init__(self, polyglot):
        super(Controller, self).__init__(polyglot)
        self.calendars = []
        self.currentDate = None
        self.poly.onConfig(self.process_config)
        self.calendarList = []

    def discover(self):
        pass

    def start(self):
        params = [
            {
                'name': 'calendarName',
                'title': 'Calendar Name',
                'desc': 'Name of the calendar in Google Calendar',
                'isRequired': True,
                'isList': True
            }
        ]
        self.poly.save_typed_params(params)

        LOGGER.info('Started HolidayGoogle Server')

        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', Controller.SCOPES)
                creds = flow.run_local_server()

            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        self.service = build('calendar', 'v3', credentials=creds)

        self.refresh()

    def longPoll(self):
        self.refresh()

    def refresh(self):
        if self.currentDate != datetime.date.today():
            self.currentDate = datetime.date.today()
            for entry in self.calendars:
                entry.todayNode.setDate(self.currentDate)
                entry.tomorrowNode.setDate(self.currentDate +
                    datetime.timedelta(days=1))

        for entry in self.calendars:
            calendar = entry.calendar
            LOGGER.debug('Checking calendar %s', calendar['summary'])
            todayDate = datetime.datetime.now(pytz.timezone(calendar['timeZone']))
            todayDate = todayDate.replace(hour=0, minute=0, second=0, microsecond=0)
            endDate = todayDate + datetime.timedelta(days=2)
            result = self.service.events().list(calendarId=calendar['id'],
                timeMin=todayDate.isoformat(), singleEvents=True,
                timeMax=endDate.isoformat()).execute()
            for event in result.get('items', []):
                if self.is_holiday(event):
                    LOGGER.debug('Event found %s', event['summary'])
                    date = dateutil.parser.parse(event['start']['date']).date()

                    if date == todayDate.date():
                        entry.todayNode.setFutureState()
                    else:
                        entry.tomorrowNode.setFutureState()
            entry.todayNode.refresh()
            entry.tomorrowNode.refresh()

    def is_holiday(self, event):
        return (event.get('transparency') == 'transparent' and
            'date' in event['start'] and
            'date' in event['end'])

    def process_config(self, config):
        self.calendars = []
        self.currentDate = None

        calendarList = {}
        pageToken = None
        while True:
            list = self.service.calendarList().list(pageToken=pageToken).execute()
            for listEntry in list['items']:
                LOGGER.debug('Found calendar %s %s', listEntry['summary'], listEntry)
                calendarList[listEntry['summary']] = listEntry
                pageToken = list.get('nextPageToken')
            if not pageToken:
                break

        typedConfig = config.get('typedCustomData')

        list = typedConfig.get('calendarName')
        calendarIndex = 0
        if list is not None:
            for calendarName in list:
                calendar = calendarList.get(calendarName)
                if calendar is None:
                    LOGGER.error('Cannot find configured calendar name %s',
                        calendarName)
                else:
                    entry = CalendarEntry(calendar,
                        DayNode(self, self.address,
                            'today' + str(calendarIndex),
                            calendar['summary'] + ' Today'),
                        DayNode(self, self.address,
                            'tmrow' + str(calendarIndex),
                            calendar['summary'] + ' Tomorrow'))
                    self.calendars.append(entry)
                    self.addNode(entry.todayNode)
                    self.addNode(entry.tomorrowNode)

                    calendarIndex += 1

        if calendarList.keys() != self.calendarList:
            self.calendarList = calendarList.keys()
            data = '<h3>Configured Calendars</h3><ul>'
            for calendarName in self.calendarList:
                data += '<li>' + calendarName + '</li>'
            data += '</ul>'
            self.poly.add_custom_config_docs(data, True)

        self.refresh()

    id = 'controller'
    commands = {'DISCOVER': discover}
    drivers = [{ 'driver': 'ST', 'value': 0, 'uom': 2 }]


class CalendarEntry(object):
    def __init__(self, calendar, todayNode, tomorrowNode):
        self.calendar = calendar
        self.todayNode = todayNode
        self.tomorrowNode = tomorrowNode


class DayNode(polyinterface.Node):
    def __init__(self, primary, controllerAddress, address, name):
        super(DayNode, self).__init__(primary, controllerAddress, address, name)
        self.futureState = False

    def setDate(self, date):
        self.setDriver('GV0', date.month)
        self.setDriver('GV1', date.day)
        self.setDriver('GV2', date.year)

    def setFutureState(self):
        self.futureState = True

    def refresh(self):
        if self.futureState:
            self.setState(True)
            self.futureState = False
        else:
            self.setState(False)

    def setState(self, state):
        self.setDriver('ST', 1 if state else 0)

    def query(self):
        self.reportDrivers()

    drivers = [
        { 'driver': 'ST', 'value': 0, 'uom': 2 },
        { 'driver': 'GV0', 'value': 0, 'uom': 47 },
        { 'driver': 'GV1', 'value': 0, 'uom': 9 },
        { 'driver': 'GV2', 'value': 0, 'uom': 77 }
    ]

    id = 'daynode'


@click.command()
def holidays_server():
    polyglot = polyinterface.Interface('HolidaysGoogleServer')
    polyglot.start()
    controller = Controller(polyglot)
    controller.name = 'Holidays Google Controller'
    controller.runForever()


if __name__ == '__main__':
    holidays_server()
