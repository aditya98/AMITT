''' Manage AMITT metadata

The AMITT github repo at https://github.com/cogsec-collaborative/AMITT serves multiple purposes:
* Holds the master copy of AMITT (in excel file AMITT_TTPs_MASTER.xlsx)
* Holds detailed notes on each phase, tactic, technique, incident, task and counter in
  AMITT.  These notes are markdown pages that people are free to suggest edits to, using git's 
  fork mechanisms. 
* Holds a list of suggested changes to AMITT, in the github repo's issues list
* Provides a set of indexed views of AMITT objects, to make exploring AMITT easier

The file in this code updates the github repo contents, after the master spreadsheet is updated. 
It creates this: 
* A html page for each AMITT TTP object (creator and counter), if it doesn't already exist.  
  If a html page does exist, update the metadata on it, and preserve any hand-created 
  notes below the metadata area in it.
* A html page for each AMITT phase, tactic, and task.
* A html page for each incident used to create AMITT
* A grid view of all the AMITT creator techniques
* A grid view of all the AMITT counter techniques
* Indexes for the counter techniques, by tactic, resource and metatag

Here are the file inputs and outputs associated with that work: 

Reads 1 excel file: ../AMITT_MASTER_DATA/AMITT_TTPs_MASTER.xlsx with sheets: 
* phases
* techniques
* tasks
* incidents
* incidenttechniques
* tactics
* countermeasures
* actortypes
* resources
* responsetypes

Reads template files:
* template_phase.md
* template_tactic.md
* template_task.md
* template_technique.md
* template_incident.md
* template_counter.md

Creates markdown files: 
* ../amitt_blue_framework.md
* ../amitt_red_framework.md
* ../amitt_red_framework_clickable.md
* ../incidents_list.md
* ../counter_tactic_counts.md
* ../metatechniques_by_responsetype.md
* ../resources_by_responsetype.md
* ../tactics_by_responsetype.md
* ../counter_tactics/*counters.md
* ../metatechniques/*.md
* ../resources_needed/*.md

Updates markdown files:
* ../phases/*.md
* ../tactics/*.md
* ../techniques/*.md
* ../incidents/*.md
* ../tasks/*.md
* ../counters/*.md

Creates CSVs
* ../generated_csvs/counters_tactics_table.csv
* ../generated_csvs/techniques_tactics_table.csv

todo: 
* add all framework comments to the repo issues list
* add clickable blue framework
* add detections
'''

import pandas as pd
import numpy as np
import os
from sklearn.feature_extraction.text import CountVectorizer


class Amitt:

    
    def __init__(self, infile = '../AMITT_MASTER_DATA/AMITT_TTPs_MASTER.xlsx'):
        
        # Load metadata from file
        metadata = {}
        xlsx = pd.ExcelFile(infile)
        for sheetname in xlsx.sheet_names:
            metadata[sheetname] = xlsx.parse(sheetname)
            metadata[sheetname].fillna('', inplace=True)

        # Create individual tables and dictionaries
        self.df_phases = metadata['phases']
        self.df_techniques = metadata['techniques']
        self.df_tasks = metadata['tasks']
        self.df_incidents = metadata['incidents']
        self.df_counters = metadata['countermeasures'].sort_values('amitt_id')
        self.df_counters[['tactic_id', 'tactic_name']] = self.df_counters['tactic'].str.split(' ', 1, expand=True)
        self.df_counters[['metatechnique_id', 'metatechnique_name']] = self.df_counters['metatechnique'].str.split(' ', 1, expand=True)
        self.df_detections = metadata['detections']
        self.df_detections[['tactic_id', 'tactic_name']] = self.df_detections['tactic'].str.split(' ', 1, expand=True)
#        self.df_detections[['metatechnique_id', 'metatechnique_name']] = self.df_detections['metatechnique'].str.split(' ', 1, expand=True) #FIXIT
        self.df_actortypes = metadata['actortypes']
        self.df_resources = metadata['resources']
        self.df_responsetypes = metadata['responsetypes']
        self.df_metatechniques = metadata['metatechniques']
        self.it = self.create_incident_technique_crosstable(metadata['incidenttechniques'])
        self.df_tactics = metadata['tactics']

        # Add columns containing lists of techniques and counters to the tactics dataframe
        self.df_techniques_per_tactic = self.df_techniques.groupby('tactic_id')['amitt_id'].apply(list).reset_index().rename({'amitt_id':'technique_ids'}, axis=1)
        self.df_counters_per_tactic = self.df_counters.groupby('tactic_id')['amitt_id'].apply(list).reset_index().rename({'amitt_id':'counter_ids'}, axis=1)
        self.df_tactics = self.df_tactics.merge(self.df_techniques_per_tactic, left_on='amitt_id', right_on='tactic_id', how='left').fillna('').drop('tactic_id', axis=1)
        self.df_tactics = self.df_tactics.merge(self.df_counters_per_tactic, left_on='amitt_id', right_on='tactic_id', how='left').fillna('').drop('tactic_id', axis=1)

        # Add simple dictionaries (id -> name) for objects
        self.phases      = self.make_object_dictionary(self.df_phases)
        self.tactics     = self.make_object_dictionary(self.df_tactics)
        self.techniques  = self.make_object_dictionary(self.df_techniques)
        self.counters    = self.make_object_dictionary(self.df_counters)
        self.metatechniques = self.make_object_dictionary(self.df_metatechniques)
        self.actortypes  = self.make_object_dictionary(self.df_actortypes)
        self.resources   = self.make_object_dictionary(self.df_resources)

        # Create the data table for each framework file
        self.num_tactics = len(self.df_tactics)

        # Create counters cross-tables
        self.cross_counterid_techniqueid = self.create_cross_table(self.df_counters[['amitt_id', 'techniques']], 
                                                                   'techniques', 'technique', '\n')        
        self.cross_counterid_resourceid = self.create_cross_table(self.df_counters[['amitt_id', 'resources_needed']], 
                                                                  'resources_needed', 'resource', ',')
        self.cross_counterid_actortypeid = self.create_cross_table(self.df_counters[['amitt_id', 'actortypes']], 
                                                                  'actortypes', 'actortype', ',')


    def create_incident_technique_crosstable(self, it_metadata):
        # Generate full cross-table between incidents and techniques

        it = it_metadata
        it.index=it['amitt_id']
        it = it['technique_ids'].str.split(',').apply(lambda x: pd.Series(x)).stack().reset_index(level=1, drop=True).to_frame('technique_id').reset_index().merge(it.drop('amitt_id', axis=1).reset_index()).drop('technique_ids', axis=1)
        it = it.merge(self.df_incidents[['amitt_id','name']], 
                      left_on='incident_id', right_on='amitt_id',
                      suffixes=['','_incident']).drop('incident_id', axis=1)
        it = it.merge(self.df_techniques[['amitt_id','name']], 
                      left_on='technique_id', right_on='amitt_id',
                      suffixes=['','_technique']).drop('technique_id', axis=1)
        return(it)


    def make_object_dictionary(self, df):
        return(pd.Series(df.name.values,index=df.amitt_id).to_dict())


    def create_cross_table(self, df, col, newcol, divider=','):
        ''' Convert a column with multiple values per cell into a crosstable

        # Thanks https://stackoverflow.com/questions/17116814/pandas-how-do-i-split-text-in-a-column-into-multiple-rows?noredirect=1
        '''
        crosstable = df.join(df[col]
                        .str.split(divider, expand=True).stack()
                        .reset_index(drop=True,level=1)
                        .rename(newcol)).drop(col, axis=1)
        crosstable = crosstable[crosstable[newcol].notnull()]
        crosstable[newcol+'_id'] = crosstable[newcol].str.split(' ').str[0]
        crosstable.drop(newcol, axis=1, inplace=True)
        return crosstable

    
    def create_technique_incidents_string(self, techniqueid):

        incidentstr = '''
| Incident | Descriptions given for this incident |
| -------- | -------------------- |
'''
        incirow = '| [{0} {1}](../incidents/{0}.md) | {2} |\n'
        its = self.it[self.it['amitt_id_technique']==techniqueid]
        for index, row in its[['amitt_id_incident', 'name_incident']].drop_duplicates().sort_values('amitt_id_incident').iterrows():
            techstring = ', '.join(its[its['amitt_id_incident']==row['amitt_id_incident']]['name'].to_list())
            incidentstr += incirow.format(row['amitt_id_incident'], row['name_incident'], techstring)
        return incidentstr


    def create_incident_techniques_string(self, incidentid):

        techstr = '''
| Technique | Description given for this incident |
| --------- | ------------------------- |
'''
        techrow = '| [{0} {1}](../techniques/{0}.md) | {2} {3} |\n'
        techlist = self.it[self.it['amitt_id_incident'] == incidentid]
        for index, row in techlist.sort_values('amitt_id_technique').iterrows():
            techstr += techrow.format(row['amitt_id_technique'], row['name_technique'], 
                                      row['amitt_id'], row['name'])
        return techstr


    def create_tactic_tasks_string(self, tactic_id):

        table_string = '''
| Tasks |
| ----- |
'''
        tactic_tasks = self.df_tasks[self.df_tasks['tactic_id']==tactic_id]
        task_string = '| [{0} {1}](../tasks/{0}.md) |\n'
        for index, row in tactic_tasks.sort_values('amitt_id').iterrows():
            table_string += task_string.format(row['amitt_id'], row['name'])
        return table_string


    def create_tactic_techniques_string(self, tactic_id):

        table_string = '''
| Techniques |
| ---------- |
'''
        tactic_techniques = self.df_techniques[self.df_techniques['tactic_id']==tactic_id]
        row_string = '| [{0} {1}](../techniques/{0}.md) |\n'
        for index, row in tactic_techniques.sort_values('amitt_id').iterrows():
            table_string += row_string.format(row['amitt_id'], row['name'])
        return table_string


    def create_object_counters_string(self, objectcolumn, object_id):
        table_string = '''
| Counters | Response types |
| -------- | -------------- |
'''
        object_counters = self.df_counters[self.df_counters[objectcolumn]==object_id]
        row_string = '| [{0} {1}](../counters/{0}.md) | {2} |\n'
        for index, row in object_counters.sort_values(['responsetype', 'amitt_id']).iterrows():
            table_string += row_string.format(row['amitt_id'], row['name'], row['responsetype'])
        return table_string

    def create_technique_counters_string(self, technique_id):
        table_string = '''
| Counters | Response types |
| -------- | -------------- |
'''
        technique_counters = self.cross_counterid_techniqueid[self.cross_counterid_techniqueid['technique_id']==technique_id]
        technique_counters = pd.merge(technique_counters, self.df_counters[['amitt_id', 'name', 'responsetype']])
        row_string = '| [{0} {1}](../counters/{0}.md) | {2} |\n'
        for index, row in technique_counters.sort_values('amitt_id').iterrows():
            table_string += row_string.format(row['amitt_id'], row['name'], row['responsetype'])
        return table_string

    def create_counter_actortypes_string(self, counter_id):
        table_string = '''
| Actor types | Sectors |
| ----------- | ------- |
'''
        counter_actortypes = self.cross_counterid_actortypeid[self.cross_counterid_actortypeid['amitt_id']==counter_id]
        counter_actortypes = pd.merge(counter_actortypes, self.df_actortypes[['amitt_id', 'name', 'sector']], left_on='actortype_id', right_on='amitt_id')
        row_string = '| [{0} {1}](../actortypes/{0}.md) | {2} |\n'
        for index, row in counter_actortypes.sort_values('actortype_id').iterrows():
            table_string += row_string.format(row['actortype_id'], row['name'], row['sector'])
        return table_string

    def create_actortype_counters_string(self, actortype_id):
        table_string = '''
| Counters | Response types |
| -------- | -------------- |
'''
        actortype_counters = self.cross_counterid_actortypeid[self.cross_counterid_actortypeid['actortype_id']==actortype_id]
        actortype_counters = pd.merge(actortype_counters, self.df_counters[['amitt_id', 'name', 'responsetype']])
        row_string = '| [{0} {1}](../counters/{0}.md) | {2} |\n'
        for index, row in actortype_counters.sort_values('amitt_id').iterrows():
            table_string += row_string.format(row['amitt_id'], row['name'], row['responsetype'])
        return table_string

    def create_resource_counters_string(self, resource_id):
        table_string = '''
| Counters | Response types |
| -------- | -------------- |
'''
        resource_counters = self.cross_counterid_resourceid[self.cross_counterid_resourceid['resource_id']==resource_id]
        resource_counters = pd.merge(resource_counters, self.df_counters[['amitt_id', 'name', 'responsetype']])
        row_string = '| [{0} {1}](../counters/{0}.md) | {2} |\n'
        for index, row in actortype_counters.sort_values('amitt_id').iterrows():
            table_string += row_string.format(row['amitt_id'], row['name'], row['responsetype'])
        return table_string


    def create_counter_tactics_string(self, counter_id):
        table_string = '''
| Counters these Tactics |
| ---------------------- |
'''
        # tactic_counters = self.df_counters[self.df_counters['tactic_id']==tactic_id]
        # row_string = '| {0} | [{1} {2}](../counters/{1}.md) |\n'
        # for index, row in tactic_counters.sort_values(['responsetype', 'amitt_id']).iterrows():
        #     table_string += row_string.format(row['responsetype'], row['amitt_id'], row['name'])
        return table_string

    def create_counter_techniques_string(self, counter_id):
        table_string = '''
| Counters these Techniques |
| ------------------------- |
'''
        counter_techniques = self.cross_counterid_techniqueid[self.cross_counterid_techniqueid['amitt_id']==counter_id]
        counter_techniques = pd.merge(counter_techniques, self.df_techniques[['amitt_id', 'name']].rename(columns={'amitt_id': 'technique_id'}))
        row_string = '| [{0} {1}](../techniques/{0}.md) |\n'
        for index, row in counter_techniques.sort_values('amitt_id').iterrows():
            table_string += row_string.format(row['technique_id'], row['name'])
        return table_string

    def create_counter_incidents_string(self, counter_id):
        table_string = '''
| Seen in incidents |
| ----------------- |
'''
        # tactic_counters = self.df_counters[self.df_counters['tactic_id']==tactic_id]
        # row_string = '| {0} | [{1} {2}](../counters/{1}.md) |\n'
        # for index, row in tactic_counters.sort_values(['responsetype', 'amitt_id']).iterrows():
        #     table_string += row_string.format(row['responsetype'], row['amitt_id'], row['name'])
        return table_string


    def write_object_index_to_file(self, objectname, objectcols, dfobject, outfile):
        ''' Write HTML version of incident list to markdown file

        Assumes that dfobject has columns named 'amitt_id' and 'name'
        '''

        html = '''# AMITT {}:

<table border="1">
<tr>
'''.format(objectname.capitalize())

        # Create header row
        html += '<th>{}</th>\n'.format('amitt_id')
        html += ''.join(['<th>{}</th>\n'.format(col) for col in objectcols])
        html += '</tr>\n'

        # Add row for each object
        for index, row in dfobject[dfobject['name'].notnull()].iterrows():
            html += '<tr>\n'
            html += '<td><a href="{0}/{1}.md">{1}</a></td>\n'.format(objectname, row['amitt_id'])
            html += ''.join(['<td>{}</td>\n'.format(row[col]) for col in objectcols])
            html += '</tr>\n'
        html += '</table>\n'

        # Write file
        with open(outfile, 'w') as f:
            f.write(html)
            print('updated {}'.format(outfile))
        return

    def write_object_indexes_to_file(self):
        ''' Create an index file for each object type.
        '''
        self.write_object_index_to_file(
            'response types', ['name', 'summary'],
            self.df_responsetypes, '../responsetype_index.md')
        self.write_object_index_to_file(
            'detections', ['name', 'summary', 'metatechnique', 'tactic', 'responsetype'],
            self.df_detections, '../detections_index.md')

        return

    def update_markdown_files(self):
        ''' Create or update all the editable markdown files in the repo

        Reads in any user-written text before updating the header information above it
        Does this for phase, tactic, technique, task, incident and counter objects
        '''

        warntext = 'DO NOT EDIT ABOVE THIS LINE - PLEASE ADD NOTES BELOW'
        warnlen = len(warntext)
        
        metadata = {
            'phase': self.df_phases,
            'tactic': self.df_tactics,
            'technique': self.df_techniques,
            'task': self.df_tasks,
            'incident': self.df_incidents,
            'counter': self.df_counters,
            'metatechnique': self.df_metatechniques,
            'actortype': self.df_actortypes,
            #'resource': self.df_resources,
            #'responsetype': self.df_responsetypes,
            #'detection': self.df_detections
        }
        
        indexrows = {
            'phase': ['name', 'summary'],
            'tactic': ['name', 'summary', 'phase_id'],
            'technique': ['name', 'summary', 'tactic_id'],
            'task': ['name', 'summary', 'tactic_id'],
            'incident': ['name', 'type', 'year_started', 'to_country', 'found_via'],
            'counter': ['name', 'summary', 'metatechnique', 'tactic', 'responsetype'],
            'detection': ['name', 'summary', 'metatechnique', 'tactic', 'responsetype'],
            'responsetype': ['name', 'summary'],
            'metatechnique': ['name', 'summary'],
            'actortype': ['name', 'summary', 'sector'],
            'resource': ['name', 'summary', 'resource type']
        }
        
        for objecttype, df in metadata.items():

            # Create objecttype directory if needed.  Create index file for objecttype
            objecttypeplural = objecttype + 's'
            objecttypedir = '../{}'.format(objecttypeplural)
            if not os.path.exists(objecttypedir):
                os.makedirs(objecttypedir)
            self.write_object_index_to_file(objecttypeplural, indexrows[objecttype],
                                            metadata[objecttype], 
                                            '../{}_index.md'.format(objecttypeplural))

            # Update or create file for every object with this objecttype type
            template = open('template_{}.md'.format(objecttype)).read()
            for index, row in df[df['name'].notnull()].iterrows():

                # First read in the file - if it exists - and grab everything 
                # below the "do not write about this line". Will write this 
                # out below new metadata. 
                datafile = '../{}/{}.md'.format(objecttypeplural, row['amitt_id'])
                oldmetatext = ''
                if os.path.exists(datafile):
                    with open(datafile) as f:
                        filetext = f.read()
                    warnpos = filetext.find(warntext)
                    if warnpos == -1:
                        print('no warning text found in {}: adding to file'.format(datafile))
                        usertext = filetext
                    else:
                        oldmetatext = filetext[:warnpos+warnlen]
                        usertext = filetext[warnpos+warnlen:]
                else:
                    usertext = ''

                # Now populate datafiles with new metadata plus old userdata
                if objecttype == 'phase':
                    metatext = template.format(type='Phase', id=row['amitt_id'], name=row['name'], summary=row['summary'])
                if objecttype == 'tactic':
                    metatext = template.format(type = 'Tactic', id=row['amitt_id'], name=row['name'],
                                               phase=row['phase_id'], summary=row['summary'],
                                               tasks=self.create_tactic_tasks_string(row['amitt_id']),
                                               techniques=self.create_tactic_techniques_string(row['amitt_id']),
                                               counters=self.create_object_counters_string('tactic_id', row['amitt_id']))
                if objecttype == 'task':
                    metatext = template.format(type='Task', id=row['amitt_id'], name=row['name'],
                                               tactic=row['tactic_id'], summary=row['summary'])
                if objecttype == 'technique':
                    metatext = template.format(type = 'Technique', id=row['amitt_id'], name=row['name'],
                                               tactic=row['tactic_id'], summary=row['summary'],
                                               incidents=self.create_technique_incidents_string(row['amitt_id']),
                                               counters=self.create_technique_counters_string(row['amitt_id']))
                if objecttype == 'counter':
                    metatext = template.format(type = 'Counter', id=row['amitt_id'], name=row['name'],
                                               tactic=row['tactic_id'], summary=row['summary'],
                                               playbooks='', metatechnique=row['metatechnique'],
                                               actortypes=self.create_counter_actortypes_string(row['amitt_id']),
                                               resources_needed=row['resources_needed'],
                                               tactics=self.create_counter_tactics_string(row['amitt_id']),
                                               techniques=self.create_counter_techniques_string(row['amitt_id']),
                                               incidents=self.create_counter_incidents_string(row['amitt_id']))
                if objecttype == 'incident':
                    metatext = template.format(type = 'Incident', id=row['amitt_id'], name=row['name'],
                                               incidenttype=row['type'], summary=row['summary'],
                                               yearstarted=row['year_started'], 
                                               fromcountry=row['from_country'],
                                               tocountry=row['to_country'],
                                               foundvia=row['found_via'],
                                               dateadded=row['when_added'],
                                               techniques=self.create_incident_techniques_string(row['amitt_id']))
                if objecttype == 'actortype':
                    metatext = template.format(type = 'Actor', id=row['amitt_id'], name=row['name'], 
                                               summary=row['summary'], sector=row['sector'],
                                               viewpoint=row['viewpoint'],
                                               counters=self.create_actortype_counters_string(row['amitt_id']))
                if objecttype == 'resource':
                    metatext = template.format(type = 'Resource', id=row['amitt_id'], name=row['name'], 
                                               summary=row['summary'], resource_type=row['resource_type'],
                                               counters=self.create_resource_counters_string(row['amitt_id']))
                if objecttype == 'metatechnique':
                    metatext = template.format(type='Metatechnique', id=row['amitt_id'], name=row['name'], 
                                               summary=row['summary'],
                                               counters=self.create_object_counters_string('metatechnique_id', row['amitt_id']))

                # Make sure the user data goes in
                if (metatext + warntext) != oldmetatext:
                    print('Updating {}'.format(datafile))
                    with open(datafile, 'w') as f:
                        f.write(metatext)
                        f.write(warntext)
                        f.write(usertext)
                        f.close()
        return


    def create_padded_framework_table(self, title, ttp_col, tocsv=True):
        # Create the master grid that we make all the framework visuals from
        # cols = number of tactics
        # rows = max number of techniques per tactic + 2

        numrows = max(self.df_tactics[ttp_col].apply(len)) + 2

        arr = [['' for i in range(self.num_tactics)] for j in range(numrows)] 
        for index, tactic in self.df_tactics.iterrows():
            arr[0][index] = tactic['phase_id']
            arr[1][index] = tactic['amitt_id']
            if tactic[ttp_col] == '':
                continue
            for index2, technique in enumerate(tactic[ttp_col]):
                arr[index2+2][index] = technique

        #Save grid to file
        if tocsv:
            snakecase_title = title.replace(' ', '_')
            csvdir = '../generated_csvs'
            if not os.path.exists(csvdir):
                os.makedirs(csvdir)
            pd.DataFrame(arr).to_csv('{0}/{1}_ids.csv'.format(csvdir, snakecase_title), index=False, header=False)

        return(arr)


    def write_amitt_frameworks(self):

        self.write_amitt_framework_files("red framework", self.techniques, "techniques", 'technique_ids')
        self.write_amitt_framework_files("blue framework", self.counters, "counters", 'counter_ids')
        return

    def write_amitt_framework_files(self, title, ttp_dictionary, ttp_dir, ttp_col):
        # Write HTML version of framework diagram to markdown file
        # Needs phases, tactics
        snakecase_title = title.replace(' ', '_')
        outfile = '../amitt_{}.md'.format(snakecase_title)
        clickable_file = '../amitt_{}_clickable.html'.format(snakecase_title)

        # Create padded table to make the writing easier
        padded_table = self.create_padded_framework_table(title, ttp_col)


        html = '''# AMITT {}: Latest Framework

<table border="1">
<tr>
'''.format(title.capitalize())

        # row with phase names in - removed because it makes the tables confusing
        # for col in range(self.num_tactics):
        #     html += '<td><a href="phases/{0}.md">{0} {1}</a></td>\n'.format(
        #         padded_table[0][col], self.phases[padded_table[0][col]])
        # html += '</tr>\n'

        html += '<tr style="background-color:blue;color:white;">\n'
        for col in range(self.num_tactics):
            html += '<td><a href="tactics/{0}.md">{0} {1}</a></td>\n'.format(
                padded_table[1][col], self.tactics[padded_table[1][col]])
        html += '</tr>\n<tr>\n'

        for row in range(2,len(padded_table)):
            for col in range(self.num_tactics):
                if padded_table[row][col] == '':
                    html += '<td> </td>\n'
                else:
                    html += '<td><a href="{0}/{1}.md">{1} {2}</a></td>\n'.format(
                        ttp_dir, padded_table[row][col], ttp_dictionary[padded_table[row][col]])
            html += '</tr>\n<tr>\n'
        html += '</tr>\n</table>\n'

        with open(outfile, 'w') as f:
            f.write(html)
            print('updated {}'.format(outfile))

        # Clickable version
        self.write_clickable_amitt_framework_file(title, padded_table, ttp_dictionary, clickable_file)

        return


    def write_clickable_amitt_framework_file(self, title, padded_table, ttp_dictionary, outfile):
        # Write clickable html version of the matrix grid to html file

        html = '''<!DOCTYPE html>
<html>
<head>
    <title>AMITT {}</title>
</head>
<body>

<script>
function handleTechniqueClick(box) {{
  var technique = document.getElementById(box);
  var checkBox = document.getElementById(box+"check");
  var text = document.getElementById(box+"text");
  if (checkBox.checked == true){{
    text.style.display = "block";
    technique.bgColor = "Lime"
  }} else {{
     text.style.display = "none";
     technique.bgColor = "Silver"
  }}
}}
</script>

<h1>AMITT</h1>

<table border=1 bgcolor=silver>
'''.format(title.capitalize())

        html += '<tr bgcolor=fuchsia>\n'
        for col in range(self.num_tactics):
            html += '<td>{0} {1}</td>\n'.format(padded_table[0][col], self.phases[padded_table[0][col]])
        html += '</tr>\n'

        html += '<tr bgcolor=aqua>\n'
        for col in range(self.num_tactics):
            html += '<td>{0} {1}</td>\n'.format(padded_table[1][col], self.tactics[padded_table[1][col]])
        html += '</tr>\n'

        liststr = ''
        html += '<tr>\n'
        for row in range(2,len(padded_table)):
            for col in range(self.num_tactics):
                techid = padded_table[row][col]
                if techid == '':
                    html += '<td bgcolor=white> </td>\n'
                else:
                    html += '<td id="{0}">{0} {1}<input type="checkbox" id="{0}check"  onclick="handleTechniqueClick(\'{0}\')"></td>\n'.format(
                        techid, ttp_dictionary[techid])
                    liststr += '<li id="{0}text" style="display:none">{0}: {1}</li>\n'.format(
                        techid, ttp_dictionary[techid])

            html += '</tr>\n<tr>\n'
        html += '</tr>\n</table>\n<hr>\n'

        html += '<ul>\n{}</ul>\n'.format(liststr)
        html += '''
</body>
</html>
'''

        with open(outfile, 'w') as f:
            f.write(html)
            print('updated {}'.format(outfile))
        return

        
    def print_technique_incidents(self):
        for id_technique in self.df_techniques['amitt_id'].to_list():
            print('{}\n{}'.format(id_technique, 
                                  self.create_incidentstring(id_technique)))
        return


    def print_incident_techniques(self):
        for id_incident in self.df_incidents['amitt_id'].to_list():
            print('{}\n{}'.format(id_incident, 
                                  self.create_techstring(id_incident)))
        return

            
    def analyse_counter_text(self, col='name'):
        # Analyse text in counter descriptions
        alltext = (' ').join(self.df_counters[col].to_list()).lower()
        count_vect = CountVectorizer(stop_words='english')
        word_counts = count_vect.fit_transform([alltext])
        dfw = pd.DataFrame(word_counts.A, columns=count_vect.get_feature_names()).transpose()
        dfw.columns = ['count']
        dfw = dfw.sort_values(by='count', ascending=False)
        return(dfw)   


    def analyse_coverage(self, technique_id_list, counter_id_list):
        ct = self.cross_counterid_techniqueid.copy()
        ct = ct[ct['technique_id'].isin(self.df_techniques['amitt_id'].to_list()) & ct['amitt_id'].isin(self.df_counters['amitt_id'].to_list())]
        possible_counters_for_techniques = ct[ct['technique_id'].isin(technique_id_list)] 
        possible_techniques_for_counters = ct[ct['technique_id'].isin(counter_id_list)] 
        coverage = ct[(ct['amitt_id'].isin(counter_id_list)) & (ct['technique_id'].isin(technique_id_list))]
        return coverage, possible_counters_for_techniques, possible_techniques_for_counters

    
    def write_counts_table_to_file(self, objectname, objectdict, counts_table, outfile):
        html = '''# AMITT {} courses of action

<table border="1">
<tr>
<td> </td>
    '''.format(objectname.capitalize())

        # Table heading row
        for col in counts_table.columns.get_level_values(1)[:-1]:
            html += '<td>{}</td>\n'.format(col)
        html += '<td>TOTALS</td></tr><tr>\n'

        # Data rows
        for index, counts in counts_table.iterrows(): 
            html += '<td><a href="../{0}s/{1}.md">{1} {2}</a></td>\n'.format(
                objectname, index, objectdict[index])
            for val in counts.values:
                html += '<td>{}</td>\n'.format(val)
            html += '</tr>\n<tr>\n'

        # Column sums
        html += '<td>TOTALS</td>\n'
        for val in counts_table.sum().values:
                html += '<td>{}</td>\n'.format(val)
        html += '</tr>\n</table>\n'           

        with open(outfile, 'w') as f:
            f.write(html)
            print('updated {}'.format(outfile))

        return


    def write_responsetype_tactics_table_file(self, outfile = '../tactics_by_responsetype_table.md'):
        ''' Write course of action matrix for tactics vs responsetype
        '''

        counts_table = pd.pivot_table(self.df_counters[['responsetype', 'tactic_id','amitt_id']], 
                                  index='tactic_id', columns='responsetype', aggfunc=len, 
                                  fill_value=0) 
        counts_table['TOTALS'] = counts_table.sum(axis=1)

        self.write_counts_table_to_file('tactic', self.tactics, counts_table, outfile)
        return


    def write_metatechniques_responsetype_table_file(self, outfile = '../metatechniques_by_responsetype_table.md'):

        counts_table = pd.pivot_table(self.df_counters[['responsetype', 'metatechnique_id','amitt_id']], 
                                  index='metatechnique_id', columns='responsetype', aggfunc=len, 
                                  fill_value=0) 
        counts_table['TOTALS'] = counts_table.sum(axis=1)

        self.write_counts_table_to_file('metatechnique', self.metatechniques, counts_table, outfile)
        return


    def write_resources_responsetype_table_file(self, outfile = '../resources_by_responsetype_table.md'):

        # dirty hack because there are lots of -blanks?- in the cross-table that should have been filtered out
        crosstable_with_responsetype = self.cross_counterid_resourceid.merge(self.df_counters[['amitt_id', 'responsetype']])
        crosstable_with_responsetype = crosstable_with_responsetype[crosstable_with_responsetype['responsetype'].isin(self.resources.keys())]
        counts_table = pd.pivot_table(crosstable_with_responsetype, 
                                  index='resource_id', columns='responsetype', aggfunc=len, 
                                  fill_value=0)
        counts_table['TOTALS'] = counts_table.sum(axis=1)

        self.write_counts_table_to_file('resource', self.resources, counts_table, outfile)
        return


    def generate_and_write_datafiles(self):

        # Framework matrices
        self.write_amitt_frameworks()
        # Editable files
        self.update_markdown_files()
        self.write_object_indexes_to_file()
        # Cross tables
        self.write_responsetype_tactics_table_file()
        self.write_metatechniques_responsetype_table_file()
        # FIXIT - this is just giving trouble today self.write_resources_responsetype_table_file()
        
        return


def main():
    amitt = Amitt()
    amitt.generate_and_write_datafiles()


if __name__ == "__main__":
    main()
