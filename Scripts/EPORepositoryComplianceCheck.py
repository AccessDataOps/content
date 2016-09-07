def generateText(tbl):
    return '\n\n'.join(['\n'.join([k + ': ' + row[k] for k in row]) for row in tbl])


def generateHtml(cols, tbl):
    html = ""
    if tbl and isinstance(tbl, list) and len(tbl) > 0:
        html = """<style type="text/css">
.tg  {border-collapse:collapse;border-spacing:0;border-color:#bbb;}
.tg td{font-family:Arial, sans-serif;font-size:14px;padding:10px 5px;border-style:solid;border-width:1px;overflow:hidden;word-break:normal;border-color:#888;color:#594F4F;}
.tg th{font-family:Arial, sans-serif;font-size:14px;font-weight:normal;padding:5px 15px 5px 5px;border-style:solid;border-width:1px;overflow:hidden;word-break:normal;border-color:#888;color:#493F3F;}
.tg .tg-9zxc{vertical-align:top;text-align:left; }
.tg .tg-x1ca{background-color:#dfdfdf;vertical-align:top;text-align:center;font-weight:bold;}
</style>
<table class="tg">
  <tr>"""
        for colName in cols:
            html += '<th class="tg-x1ca">' + colName + '</th>'
        html += '</tr>'
        for row in tbl:
            html += '<tr>'
            for colName in cols:
                html += '<th class="tg-9zxc">' + flattenCell(row[colName]).replace('\n','<br/>') + '</th>'
            html += '</tr>'
        html += '</table>'
    return html

FAULTY_THRESHOLD = 2.0
res = []
repos = demisto.get(demisto.args(), 'repostocheck')
if not repos:
    res.append({"Type": entryTypes["error"], "ContentsFormat": formats["text"], "Contents": "Received empty repository list!"})
else:
    repos = ','.join(repos) if isinstance(repos, list) else repos
    reqDat = demisto.get(demisto.args(), 'requireddatversion')
    # Find the VSCANDAT1000 Package
    dArgs = {"using": repos,
             "command": "repository.findPackages",
             "params": "searchText=VSCANDAT1000"
            }
    noncompliant = []
    faulty = {}
    tbl = []
    resCmdName = demisto.executeCommand('epo-command', dArgs)
    try:
        for entry in resCmdName:
            if isError(entry):
                res = resCmdName
                break
            else:
                repoName = entry['ModuleName']
                myData = demisto.get(entry, 'Contents.response')[0]['productDetectionProductVersion']
                if float(myData)<float(reqDat):
                    if (float(reqDat) - float(myData)) >= FAULTY_THRESHOLD:
                        status = "Faulty"
                        faulty[repoName] = str(myData)
                    else:
                        status = "Not compliant"
                    noncompliant.append(repoName)
                    #demisto.log(repoName + ' is noncompliant - using DAT version ' + myData)
                else:
                    status = "OK"
                    #demisto.log(repoName + ' is OK - using DAT version ' + myData)
                tbl.append({'Repository': repoName, 'Version of DAT': myData, 'Status': status })
    except Exception as ex:
        res.append({"Type": entryTypes["error"], "ContentsFormat": formats["text"],
                    "Contents": "Error occurred while parsing output from command. Exception info:\n" + str(ex) + "\n\nInvalid output:\n" + str(resCmdName)})

    demisto.setContext('olddatrepos', noncompliant)
    demisto.setContext('faultyrepos', faulty.keys())
    demisto.setContext('faultyrepostext', "The following repositories were found to be faulty with old DAT versions:\n" + '\n'.join([k + ': DAT version ' + faulty[k] for k in faulty]))
    demisto.setContext('repocomplianceresultshtml', generateHtml(('Repository', 'Version of DAT', 'Status'), tbl))
    demisto.setContext('repocomplianceresultstext', generateText(tbl))
    res.append({"Type": entryTypes["note"], "ContentsFormat": formats["table"], "Contents": tbl})
    answer = "yes" if noncompliant else "no"
    res.append({"Type": entryTypes["note"], "ContentsFormat": formats["text"], "Contents": answer})
demisto.results(res)
