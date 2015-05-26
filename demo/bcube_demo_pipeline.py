import json
import glob
import luigi
import os
from dlib.task_helpers import parse_yaml, extract_task_config
from dlib.task_helpers import read_data, generate_output_filename, run_init
from dlib.identifier import Identify
from dlib.parser import Parser
from dlib.process_router import Processor
from dlib.btriples import triplify, serialize


'''
pipeline for the demo
1. pull from solr
2. convert
3. identify
4. parse
5. triples
'''


class RawTask(luigi.Task):
    yaml_file = luigi.Parameter()
    input_file = luigi.Parameter()

    output_path = ''

    def requires(self):
        return []

    def output(self):
        return luigi.LocalTarget(
            generate_output_filename(
                self.input_file,
                self.output_path,
                'raw'
            ))

    def run(self):
        ''' '''
        self._configure()

        data = read_data(self.input_file)
        new_data = self.process_response(data)

        with self.output().open('w') as out_file:
            out_file.write(json.dumps(new_data, indent=4))

    def process_response(self, data):
        '''
        get the sha, the content, the url, and the harvest date
        '''
        content = data.get('raw_content', '').encode('unicode_escape')
        content = content[content.index('<'):]
        content = content.replace('\\n', ' ').replace('\\t', ' ')
        content = content.replace('\\\\ufffd', ' ').replace('\\ufffd', ' ')
        content = ' '.join(content.split())
        content = content.strip()

        url = data.get('url', '')
        sha = data.get('sha', '')
        harvest = data.get('tstamp', '')
        return {
            "content": content,
            "url": url,
            "sha": sha,
            "harvest": harvest
        }

    def _configure(self):
        config = parse_yaml(self.yaml_file)
        config = extract_task_config(config, 'Raw')
        self.output_path = config.get('output_directory', '')


class IdentifyTask(luigi.Task):
    yaml_file = luigi.Parameter()
    input_file = luigi.Parameter()

    output_path = ''
    identifiers = []

    def requires(self):
        return RawTask(input_file=self.input_file, yaml_file=self.yaml_file)

    def output(self):
        return luigi.LocalTarget(
            generate_output_filename(
                self.input_file,
                self.output_path,
                'identified'
            ))

    def run(self):
        ''' '''
        self._configure()

        f = self.input().open('r')
        data = json.loads(f.read())
        new_data = self.process_response(data)

        with self.output().open('w') as out_file:
            out_file.write(json.dumps(new_data, indent=4))

    def _configure(self):
        config = parse_yaml(self.yaml_file)
        config = extract_task_config(config, 'Identify')
        self.output_path = config.get('output_directory', '')
        self.identifiers = config.get('identifiers', [])

    def process_response(self, data):
        ''' check against the yaml config '''
        content = data.get('content', '').encode('unicode_escape')
        url = data.get('url', '')
        parser = Parser(content)

        identifier = Identify(
            self.identifiers,
            content,
            url,
            **{'parser': parser, 'ignore_case': True}
        )
        identifier.identify()
        data['identity'] = identifier.to_json()
        return data


class ParseTask(luigi.Task):
    yaml_file = luigi.Parameter()
    input_file = luigi.Parameter()

    output_path = ''
    params = {}

    def requires(self):
        return IdentifyTask(input_file=self.input_file, yaml_file=self.yaml_file)

    def output(self):
        return luigi.LocalTarget(
            generate_output_filename(
                self.input_file,
                self.output_path,
                'parsed'
            ))

    def run(self):
        ''' '''
        self._configure()

        f = self.input().open('r')
        data = json.loads(f.read())
        new_data = self.process_response(data)

        with self.output().open('w') as out_file:
            out_file.write(json.dumps(new_data, indent=4))

    def _configure(self):
        config = parse_yaml(self.yaml_file)
        config = extract_task_config(config, 'Parse')
        self.output_path = config.get('output_directory', '')
        self.params = config.get('params', {})

    def process_response(self, data):
        content = data.get('content', '').encode('unicode_escape')
        url = data.get('url', '')
        identity = data.get('identity', {})

        processor = Processor(identity, content, url)
        if not processor:
            return {}

        description = processor.reader.parse_service()
        description['solr_identifier'] = data['sha']
        description['source_url'] = url
        del data['content']
        data['service_description'] = description
        return data


class TripleTask(luigi.Task):
    yaml_file = luigi.Parameter()
    input_file = luigi.Parameter()

    output_path = ''
    params = {}

    def requires(self):
        return ParseTask(input_file=self.input_file, yaml_file=self.yaml_file)

    def output(self):
        return luigi.LocalTarget(
            generate_output_filename(
                self.input_file,
                self.output_path,
                'triples',
                '.ttl'
            ))

    def run(self):
        ''' '''
        self._configure()

        f = self.input().open('r')
        data = json.loads(f.read())
        new_data = self.process_response(data)
        if new_data is not None:
            with self.output().open('w') as out_file:
                out_file.write(json.dumps(new_data, indent=4))

    def _configure(self):
        config = parse_yaml(self.yaml_file)
        config = extract_task_config(config, 'Triple')
        self.output_path = config.get('output_directory', '')
        self.params = config.get('params', {})

    def process_response(self, data):
        graph = triplify(data, None)
        if graph is not None:
            graph = serialize(graph)
        return graph


class MainWorkflow(luigi.Task):
    doc_dir = luigi.Parameter()
    yaml_file = luigi.Parameter()

    def requires(self):
        return [TripleTask(input_file=f, yaml_file=self.yaml_file) for f in self._iterator()]

    def output(self):
        return luigi.LocalTarget('log.txt')

    def run(self):
        self._configure()

    def _configure(self):
        config = parse_yaml(self.yaml_file)
        run_init(config)

    def _iterator(self):
        for f in glob.glob(os.path.join(self.doc_dir, '*.json')):
            yield f
