"""Base Integration for Cortex XSOAR (aka Demisto)

This is an empty Integration with some basic structure according
to the code conventions.

MAKE SURE YOU REVIEW/REPLACE ALL THE COMMENTS MARKED AS "TODO"

Developer Documentation: https://xsoar.pan.dev/docs/welcome
Code Conventions: https://xsoar.pan.dev/docs/integrations/code-conventions
Linting: https://xsoar.pan.dev/docs/integrations/linting

This is an empty structure file. Check an example at;
https://github.com/demisto/content/blob/master/Packs/HelloWorld/Integrations/HelloWorld/HelloWorld.py

"""

import demistomock as demisto
from CommonServerPython import *  # noqa # pylint: disable=unused-wildcard-import
from CommonServerUserPython import *  # noqa

import requests
import traceback
import httplib2
import urllib.parse
from googleapiclient.discovery import build, Resource
from oauth2client import service_account

# This is a message in the oath2client branch
SERVICE_ACCOUNT_FILE = 'token.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Disable insecure warnings
requests.packages.urllib3.disable_warnings()  # pylint: disable=no-member

''' CONSTANTS '''

DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'  # ISO8601 format with UTC, default in XSOAR


# HELPER FUNCTIONS

def prepare_result(response: dict, args: dict) -> CommandResults:
    """
        This function is for the UPDATE command result formatting
        echo_spreadsheat is false then the HR will be only success or failed,
        and the output will be empty.
        if echo_spreadsheet is true then we prepare the HR and substitute the response to the output

        input:
            response: the response from the google API
            args: demisto.args
        output: the command result of the function
    """
    markdown = '### Success\n'
    outputs = None
    if argToBoolean(args.get('echo_spreadsheet')):
        # here will be the code that will prep the result if echo is mode is on
        human_readable = {
            'spreadsheet Id': response.get('spreadsheetId'),
            'spreadsheet url': response.get('updatedSpreadsheet', {}).get('spreadsheetUrl')
        }

        table_title = response.get('updatedSpreadsheet', {}).get('properties', {}).get('title', '')
        markdown += tableToMarkdown(table_title, human_readable,
                                    headers=['spreadsheet Id', 'spreadsheet url'])
        markdown += '\n'
        sheets = response.get('updatedSpreadsheet', {}).get('sheets')  # this is an array of sheet dicts

        markdown += tableToMarkdown('Content', create_list_id_title(sheets), headers=['SheetId', 'Sheet title'])
        outputs = response

    results = CommandResults(
        readable_output=markdown,
        outputs_prefix='Spreadsheet',
        outputs_key_field='spreadsheetId',
        outputs=outputs
    )

    return results


def create_list_id_title(sheets: list) -> list:
    """
        input: this function gets a list of all the sheets of a spreadsheet
                a sheet is represented as a dict format with the following fields
                 "sheets" : [
                  {
                    "properties": {
                      "sheetId": 0,
                      "title": "Sheet1",
                      "index": 0,
                      "sheetType": "GRID",
                      "gridProperties": {
                        "rowCount": 1000,
                        "columnCount": 26
                      }
                    }
                  },
                  ...
                  ]

        output :
            the output of the function will be a list of dict in the format
            [...{'sheetId' : 123 , 'sheet title': 'title'}...]
    """
    result = []
    for sheet in sheets:
        sheetId = sheet.get('properties').get('sheetId')
        sheet_title = sheet.get('properties').get('title')
        result.append({'SheetId': sheetId, 'Sheet title': sheet_title})
    return result


def handle_values_input(values: str) -> list:
    """
    input: a string representation of values in the form of "[1,2,3],[4,5,6]..."
    output: a list of list of the values for this example [[1,2,3],[4,5,6]...]
    """
    # TODO check if this is none
    split_by_brackets = re.findall("\[(.*?)\]", values)
    res_for_values_req = []
    # split each element by that was in the brackets by a comma
    for element in split_by_brackets:
        res_for_values_req.append(element.split(","))

    return res_for_values_req


def markdown_single_get(response: dict) -> str:
    """
        creates for a single spreadsheet a mark down with 2 tables
        table 1: spreadsheet id and title
        table 2: all the sheets under this spreadsheet id and title
    """
    human_readable = {
        'spreadsheet Id': response.get('spreadsheetId', {}),
        'spreadsheet url': response.get('spreadsheetUrl', {}),
    }

    markdown = tableToMarkdown(response.get('properties', {}).get('title', {}), human_readable,
                               headers=['spreadsheet Id', 'spreadsheet url'])

    markdown += '\n'
    sheets = response.get('sheets', [])
    sheets_titles = create_list_id_title(list(sheets))
    markdown += tableToMarkdown('Content', sheets_titles, headers=['SheetId', 'Sheet title'])
    return markdown


def create_spreadsheet(service: Resource, args: dict) -> CommandResults:
    '''
        input: service - google-api discovery resource (google api client)
                args - demisto.args() for the api call
        output : command result
        action : creats a new spreadsheet
    '''
    # in this function I can set them to None and then remove them in
    # the next function, or I can set them manually to the default value.
    rgb_format = argToList(args.get('cell_format_backgroundColor'))
    rgb_format = [1, 1, 1, 1] if not rgb_format else rgb_format
    spreadsheet = {
        "properties": {
            "title": args.get('title'),
            "locale": args.get('locale', "en"),
            "defaultFormat": {
                "numberFormat": {
                    "type": args.get('cell_form_at_type', 'TEXT')
                },
                "backgroundColor": {
                    "red": rgb_format[0],
                    "green": rgb_format[1],
                    "blue": rgb_format[2],
                    "alpha": rgb_format[3]
                },
                "textFormat": {
                    "fontFamily": args.get('cell_format_textformat_family', 'ariel'),
                    "fontSize": args.get('cell_format_textformat_font_size', 11)
                },
                "textDirection": args.get('cell_format_text_direction', 'LEFT_TO_RIGHT')
            }
        },
        "sheets": [
            {
                "properties": {
                    "title": args.get('sheet_title'),
                    "sheetType": args.get('sheet_type', "GRID")
                }
            }
        ]
    }
    # this removes all None values from the json in a recursive manner.
    spreadsheet = remove_empty_elements(spreadsheet)
    response = service.spreadsheets().create(body=spreadsheet).execute()

    human_readable = {
        'spreadsheet Id': response.get('spreadsheetId'),
        'spreadsheet title': response.get('properties').get('title')
    }
    markdown = tableToMarkdown('Success', human_readable, headers=['spreadsheet Id', 'spreadsheet title'])
    results = CommandResults(
        readable_output=markdown,
        outputs_prefix='Spreadsheet',
        outputs_key_field='spreadsheetId',
        outputs=response
    )
    return results


def sheets_spreadsheet_update(service: Resource, args: dict) -> CommandResults:
    '''
       input: service - google-api discovery resource (google api client)
               args - demisto.args() for the api call
       output : command result
       action : updates a spreadsheet by a user costume update request
    '''
    spreadsheet_id = args.get('spreadsheet_id')
    request_to_update = safe_load_json(args.get('requests'))
    response = service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=request_to_update).execute()
    return prepare_result(response, args)


def get_spreadsheet(service: Resource, args: dict) -> CommandResults:
    '''
        input: service - google-api discovery resource (google api client)
                args - demisto.args() for the api call
        output : command result
        action : gets a single or multiple spreadsheets
    '''
    spread_sheets_ids = argToList(args.get('spreadsheet_id'))
    include_grid_data = args.get('include_grid_data', False)
    # The ranges to retrieve from the spreadsheet.
    ranges = args.get('ranges')
    markdown = ""
    if len(spread_sheets_ids) > 1:
        for spreadsheet in spread_sheets_ids:
            response = service.spreadsheets().get(spreadsheetId=spreadsheet).execute()
            markdown += markdown_single_get(response)
            markdown += '---\n'

        markdown = '### Success\n' + markdown
        return CommandResults(readable_output=markdown)

    else:
        request = service.spreadsheets().get(spreadsheetId=spread_sheets_ids[0], ranges=ranges,
                                             includeGridData=include_grid_data)
        response = request.execute()
        markdown = markdown_single_get(response)
        markdown = '### Success\n' + markdown

        results = CommandResults(
            readable_output=markdown,
            outputs_prefix='Spreadsheet',
            outputs_key_field='spreadsheetId',
            outputs=response
        )
        return results

    # True if grid data should be returned.
    # This parameter is ignored if a field mask was set in the request.


def sheet_create(service: Resource, args: dict) -> CommandResults:
    '''
        input: service - google-api discovery resource (google api client)
                args - demisto.args() for the api call
        output : command result
        action: creates a new sheet in a spreadsheet
    '''
    spreadsheet_id = args.get('spreadsheet_id')
    rgb_format = argToList(args.get('tab_color'))
    rgb_format = [1, 1, 1, 1] if not rgb_format else rgb_format
    request_to_update = {
        "requests": [
            {
                "addSheet": {
                    "properties": {
                        "sheetId": args.get('sheet_id', None),
                        "title": args.get('sheet_title', None),
                        "index": args.get('sheet_index', None),
                        "sheetType": args.get('sheet_type', "GRID"),
                        "rightToLeft": args.get('right_to_left', None),
                        "tabColor": {
                            "red": rgb_format[0],
                            "green": rgb_format[1],
                            "blue": rgb_format[2],
                            "alpha": rgb_format[3]
                        },
                        "hidden": args.get('hidden', False)
                    }
                }
            }
        ],
        "includeSpreadsheetInResponse": args.get('echo_spreadsheet')
    }
    request_to_update = remove_empty_elements(request_to_update)
    response = service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=request_to_update).execute()
    results = prepare_result(response, args)
    return results


def sheet_duplicate(service: Resource, args: dict) -> CommandResults:
    '''
        input: service - google-api discovery resource (google api client)
                args - demisto.args() for the api call
        output : the command result containing the duplicate spreadsheet sheet update api call
        action : duplicates a sheet within a spreadsheet
    '''
    spreadsheet_id = args.get('spreadsheet_id')
    request_to_update = {
        "requests": [
            {
                "duplicateSheet": {
                    "sourceSheetId": args.get('source_sheet_id'),
                    "insertSheetIndex": args.get('new_sheet_index'),
                    "newSheetName": args.get('new_sheet_name')
                }
            }
        ],
        "includeSpreadsheetInResponse": args.get('echo_spreadsheet')
    }

    response = service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=request_to_update).execute()
    results = prepare_result(response, args)
    return results


def sheet_copy_to(service: Resource, args: dict) -> CommandResults:
    '''
        input: service - google-api discovery resource (google api client)
                args - demisto.args() for the api call
        output : Command result with only readable output
        action : copies a spreadsheet sheet from one spreadsheet to another
    '''
    spreadsheet_id_to_copy = args.get('source_spreadsheet_id')

    # The ID of the sheet to copy.
    sheet_id_to_copy = args.get('source_sheet_id')

    copy_sheet_to_another_spreadsheet_request_body = {
        # The ID of the spreadsheet to copy the sheet to.
        'destination_spreadsheet_id': args.get('destination_spreadsheet_id')
    }

    request = service.spreadsheets().sheets().copyTo(spreadsheetId=spreadsheet_id_to_copy, sheetId=sheet_id_to_copy,
                                                     body=copy_sheet_to_another_spreadsheet_request_body)
    request.execute()  # we dont save the response because we dont need to add this to the context or the HR
    results = CommandResults(
        readable_output="### Success"
    )

    return results


def sheet_delete(service: Resource, args: dict) -> CommandResults:
    '''
        input: service - google-api discovery resource (google api client)
                args - demisto.args() for the api call
        output : Command result
        action : deletes a sheet from a spreadsheet
    '''
    spreadsheet_id = args.get('spreadsheet_id')
    request_to_update = {
        "requests": [
            {
                "deleteSheet": {
                    "sheetId": args.get('sheet_id')
                }
            }
        ],
        "includeSpreadsheetInResponse": args.get('echo_spreadsheet')
    }

    response = service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=request_to_update).execute()
    results = prepare_result(response, args)
    return results


def sheet_clear(service: Resource, args: dict) -> CommandResults:
    '''
         input: service - google-api discovery resource (google api client)
                 args - demisto.args() for the api call
         output : Command result
         action : clears a sheet from a spreadsheet
     '''
    spreadsheet_id = args.get('spreadsheet_id')
    ranges = args.get('range')

    # the body of this reqeust needs to be empty
    request = service.spreadsheets().values().clear(spreadsheetId=spreadsheet_id, range=ranges,
                                                    body={})
    request.execute()  # we don't save the response because there is no need for output or HR
    results = CommandResults(
        readable_output='### Success'
    )
    return results


def sheet_dimension_delete(service: Resource, args: dict) -> CommandResults:
    '''
         input: service - google-api discovery resource (google api client)
                 args - demisto.args() for the api call
         output : Command result
         action : deletes a specified dimension from a sheet in a specified spreadsheet
     '''
    spreadsheet_id = args.get('spreadsheet_id')

    request_to_update = {
        "requests": [
            {
                "deleteDimension": {
                    "range": {
                        "dimension": args.get('dimension_type'),
                        "sheetId": args.get('sheet_id'),
                        "startIndex": args.get('start_index'),
                        "endIndex": args.get('end_index')
                    }
                }
            }
        ],
        "includeSpreadsheetInResponse": args.get('echo_spreadsheet')
    }
    request_to_update = remove_empty_elements(request_to_update)
    response = service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=request_to_update).execute()
    results = prepare_result(response, args)
    return results


def sheet_range_delete(service: Resource, args: dict) -> CommandResults:
    '''
       input: service - google-api discovery resource (google api client)
               args - demisto.args() for the api call
       output : Command result
       action : deletes a specified range from a sheet in a specified spreadsheet
    '''
    spreadsheet_id = args.get('spreadsheet_id')

    request_to_update = {
        "requests": [
            {
                "deleteRange": {
                    "range": {
                        "sheetId": args.get('sheet_id'),
                        "startRowIndex": args.get('start_row_index'),
                        "endRowIndex": args.get('end_row_index'),
                        "startColumnIndex": args.get('start_column_index'),
                        "endColumnIndex": args.get('end_column_index')
                    },
                    "shiftDimension": args.get('shift_dimension')
                }
            }
        ],
        "includeSpreadsheetInResponse": args.get('echo_spreadsheet')
    }
    request_to_update = remove_empty_elements(request_to_update)
    response = service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=request_to_update).execute()
    results = prepare_result(response, args)
    return results


def sheets_data_paste(service: Resource, args: dict) -> CommandResults:
    '''
       input: service - google-api discovery resource (google api client)
               args - demisto.args() for the api call
       output : Command result
       action : inserts data into a spreadsheet sheet
    '''
    spreadsheet_id = args.get('spreadsheet_id')
    request_to_update = {
        "requests": [
            {
                "pasteData": {
                    "coordinate": {
                        "sheetId": args.get('sheet_id'),
                        "rowIndex": args.get('row_index'),
                        "columnIndex": args.get('column_index')
                    },
                    "data": args.get('data'),  # check here the data comes as an array how to handle
                    "type": f"PASTE_{args.get('paste_type')}",  # add paste before the type
                }
            }
        ],
        "includeSpreadsheetInResponse": args.get('echo_spreadsheet', None)
    }
    request_to_update = remove_empty_elements(request_to_update)
    kind = args.get('data_kind')
    data_paste_req = request_to_update.get('requests')[0].get('pasteData')
    if kind == 'delimiter':
        data_paste_req[kind] = ','
    else:
        data_paste_req[kind] = "true"

    request_to_update = remove_empty_elements(request_to_update)
    response = service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=request_to_update).execute()
    results = prepare_result(response, args)
    return results


def sheets_find_replace(service: Resource, args: dict) -> CommandResults:
    '''
       input: service - google-api discovery resource (google api client)
               args - demisto.args() for the api call
       output : Command result
       action : finds a vaule in the spreadsheets sheet and replaces it.
    '''
    spreadsheet_id = args.get('spreadsheet_id')
    request_to_update = {
        "requests": [
            {
                "findReplace": {
                    "find": args.get('find'),
                    "replacement": args.get('replacement'),
                    "sheetId": args.get('sheet_id'),
                    "allSheets": args.get('all_sheets'),
                    "matchCase": args.get('match_case'),
                    "matchEntireCell": args.get('match_entire_cell'),
                    "range": {
                        "sheetId": args.get('range_sheet_id'),
                        "startRowIndex": args.get('range_start_row_Index'),
                        "endRowIndex": args.get('range_end_row_Index'),
                        "startColumnIndex": args.get('range_start_column_Index'),
                        "endColumnIndex": args.get('range_end_column_Index')
                    }
                }
            }
        ],
        "includeSpreadsheetInResponse": args.get('echo_spreadsheet')
    }

    request_to_update = remove_empty_elements(request_to_update)
    response = service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=request_to_update).execute()
    results = prepare_result(response, args)
    return results


def sheets_value_update(service: Resource, args: dict) -> CommandResults:
    '''
       input: service - google-api discovery resource (google api client)
               args - demisto.args() for the api call
       output : Command result
       action : updates values in the spreadsheets sheet
    '''
    spreadsheet_id = args.get('spreadsheet_id')
    input_option = args.get('input_option')
    ranges = args.get('range')
    value_range_body = {
        "majorDimension": args.get('major_dimension'),
        "values": handle_values_input(str(args.get('values')))
    }
    request = service.spreadsheets().values().update(spreadsheetId=spreadsheet_id, range=ranges,
                                                     valueInputOption=input_option, body=value_range_body)
    request.execute()
    markdown = '### Success\n'
    return CommandResults(readable_output=markdown)


def sheets_value_append(service: Resource, args: dict) -> CommandResults:
    '''
         input: service - google-api discovery resource (google api client)
                 args - demisto.args() for the api call
         output : Command result
         action : appends values to a spreadsheets sheet
    '''
    spreadsheet_id = args.get('spreadsheet_id')
    range_ = args.get('range')
    input_option = args.get('input_option')
    insert_option = args.get('insert_option')

    value_range_body = {
        "majorDimension": args.get('major_dimension'),
        # TODO: check about the element types what how does it work
        "values": handle_values_input(str(args.get("values")))
    }
    request = service.spreadsheets().values().append(spreadsheetId=spreadsheet_id, range=range_,
                                                     valueInputOption=input_option,
                                                     insertDataOption=insert_option, body=value_range_body)
    request.execute()

    markdown = '### Success\n'
    return CommandResults(readable_output=markdown)


# disable-secrets-detection-start
# @staticmethod
def get_http_client_with_proxy(proxy: bool, insecure: bool):
    """
    Create an http client with proxy with whom to use when using a proxy.
    :param proxy: Whether to use a proxy.
    :param insecure: Whether to disable ssl and use an insecure connection.
    :return:
    """
    if proxy:
        proxies = handle_proxy()
        https_proxy = proxies.get('https')
        http_proxy = proxies.get('http')
        proxy_conf = https_proxy if https_proxy else http_proxy
        # if no proxy_conf - ignore proxy
        if proxy_conf:
            if not proxy_conf.startswith('https') and not proxy_conf.startswith('http'):
                proxy_conf = 'https://' + proxy_conf
            parsed_proxy = urllib.parse.urlparse(proxy_conf)
            proxy_info = httplib2.ProxyInfo(
                proxy_type=httplib2.socks.PROXY_TYPE_HTTP,
                proxy_host=parsed_proxy.hostname,
                proxy_port=parsed_proxy.port,
                proxy_user=parsed_proxy.username,
                proxy_pass=parsed_proxy.password)
            return httplib2.Http(proxy_info=proxy_info, disable_ssl_certificate_validation=insecure)
    return httplib2.Http(disable_ssl_certificate_validation=insecure)


def build_and_authenticate(params: dict):
    """
    Return a service object via which can call GRM API.

    Use the service_account credential file generated in the Google Cloud
    Platform to build the Google Resource Manager API Service object.

    returns: service
        Google Resource Manager API Service object via which commands in the
        integration will make API calls
    """
    service_account_credentials = params.get('service_account_credentials', {})
    service_account_credentials = json.loads(service_account_credentials.get('password'))
    credentials = service_account.ServiceAccountCredentials.from_json_keyfile_dict(service_account_credentials,
                                                                                   scopes=SCOPES)
    # add delegation to help manage the UI - link to a google-account
    if params.get('user_id', None) is not None:
        credentials = credentials.create_delegated(params.get('user_id'))

    proxy = params.get('proxy', False)
    disable_ssl = params.get('insecure', False)

    if proxy or disable_ssl:
        http_client = credentials.authorize(get_http_client_with_proxy(proxy, disable_ssl))
        return build('sheets', 'v4', http=http_client)
    else:
        return build('sheets', 'v4', credentials=credentials)


def test_module() -> str:
    return "ok"


''' MAIN FUNCTION '''

# THIS IS A COMMENT


def main() -> None:
    """main function, parses params and runs command functions
    :return:
    :rtype:
    """

    demisto.debug(f'Command being called is {demisto.command()}')

    try:
        service = build_and_authenticate(demisto.params())
        if demisto.command() == 'test-module':
            return_results(test_module())
        elif demisto.command() == 'google-sheets-spreadsheet-create':
            return_results(create_spreadsheet(service, demisto.args()))
        elif demisto.command() == 'google-sheets-spreadsheet-get':
            return_results(get_spreadsheet(service, demisto.args()))
        elif demisto.command() == 'google-sheets-spreadsheet-update':
            return_results(sheets_spreadsheet_update(service, demisto.args()))
        elif demisto.command() == 'google-sheets-sheet-create':
            return_results(sheet_create(service, demisto.args()))
        elif demisto.command() == 'google-sheets-sheet-duplicate':
            return_results(sheet_duplicate(service, demisto.args()))
        elif demisto.command() == 'google-sheets-sheet-copy-to':
            return_results(sheet_copy_to(service, demisto.args()))
        elif demisto.command() == 'google-sheets-sheet-delete':
            return_results(sheet_delete(service, demisto.args()))
        elif demisto.command() == 'google-sheets-sheet-clear':
            return_results(sheet_clear(service, demisto.args()))
        elif demisto.command() == 'google-sheets-dimension-delete':
            return_results(sheet_dimension_delete(service, demisto.args()))
        elif demisto.command() == 'google-sheets-range-delete':
            return_results(sheet_range_delete(service, demisto.args()))
        elif demisto.command() == 'google-sheets-data-paste':
            return_results(sheets_data_paste(service, demisto.args()))
        elif demisto.command() == 'google-sheets-find-replace':
            return_results(sheets_find_replace(service, demisto.args()))
        elif demisto.command() == 'google-sheets-value-update':
            return_results(sheets_value_update(service, demisto.args()))
        elif demisto.command() == 'google-sheets-value-append':
            return_results(sheets_value_append(service, demisto.args()))
        else:
            raise NotImplementedError('Command "{}" is not implemented.'.format(demisto.command()))

    # Log exceptions and return errors
    except Exception as e:
        demisto.error(traceback.format_exc())  # print the traceback
        return_error(f'Failed to execute {demisto.command()} command.\nError:\n{str(e)}')


''' ENTRY POINT '''

if __name__ in ('__main__', '__builtin__', 'builtins'):
    main()
