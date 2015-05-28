# -*- coding: utf-8 -*-

import flask
from flask import Flask
from flask import Response
from flask import request
app = Flask(__name__)

import luigi
from luigi import worker
import os
from bcube_demo_pipeline import MainWorkflow
from dlib.task_helpers import clear_directory
from dlib.call_solr import pull_from_solr
from dlib.btriples import storify

import sys
import StringIO
import glob


@app.route('/pipe')
def trigger_pipeline():
    '''
    run the pipeline
    '''
    doc_dir = 'bcube_demo/docs'

    # capture the main luigi output
    ste = sys.stderr
    sys.stderr = pipeline_output = StringIO.StringIO()
    std = sys.stdout
    sys.stdout = pipeline_debug = StringIO.StringIO()

    pull_from_solr(doc_dir)
    task = MainWorkflow(doc_dir=doc_dir, yaml_file='configs/bcube_demo.yaml')
    luigi.interface.setup_interface_logging()
    sch = luigi.scheduler.CentralPlannerScheduler()
    w = worker.Worker(scheduler=sch)
    w.add(task)
    w.run()

    # store and reset
    piped = pipeline_output.getvalue()
    sys.stderr = ste

    debugs = pipeline_debug.getvalue()
    sys.stdout = std

    # # fake the generator
    # def generate():
    #     for pipe in piped.split('\n'):
    #         yield pipe + '\n'
    #     yield '\n\n####################\n\n'

    #     for debug in debugs.split('\n'):
    #         yield debug + '\n'

    # return Response(generate(), mimetype='text/plain')

    def generate_urn():
        for urn in glob.glob('bcube_demo/triples/*.txt'):
            with open(urn, 'r') as f:
                u = f.read().strip()
            yield u + '\n'
    return Response(generate_urn(), mimetype='text/plain')


@app.route('/reset')
def reset():
    '''
    reset the pipeline (delete the intermediate files)
    '''
    # TODO: remove the TRIPLES acting on EACH file first.
    endpoint = 'http://54.69.87.196:8080/parliament/sparql'
    for ttl in glob.glob(os.path.join('bcube_demo', 'triples', '*.ttl')):
        storify(endpoint, triples_path=ttl, option='DELETE')

    dirs = ['docs', 'raw', 'identified', 'parsed', 'triples']
    for d in dirs:
        clear_directory(os.path.join('bcube_demo', d))
    return 'Pipeline reset!'

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)
