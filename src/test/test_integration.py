import unittest
import json
import time
import requests
from confluent_kafka import Producer
from src.utils.config import get_config
from src.utils.re_client import get_doc, get_edge

_CONFIG = get_config()


class TestIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print('token', _CONFIG['ws_token'])
        # Initialize specs
        print('Initializing specs for the RE API..')
        resp = requests.put(
            _CONFIG['re_api_url'] + '/api/v1/specs',
            headers={'Authorization': _CONFIG['ws_token']},
            params={'init_collections': '1'}
        )
        resp.raise_for_status()
        print('Done initializing RE specs.')

    def test_basic(self):
        """
        Test a full successful object import into arango, checking for all associated documents.
        """
        _produce({'evtype': 'NEW_VERSION', 'wsid': 41347, 'objid': 5, 'ver': 1})
        time.sleep(30)
        # Check for wsfull_object
        obj_doc = _wait_for_doc('wsfull_object', '41347:5')
        self.assertEqual(obj_doc['workspace_id'], 41347)
        self.assertEqual(obj_doc['object_id'], 5)
        self.assertEqual(obj_doc['deleted'], False)
        hsh = "0e8d1a5090be7c4e9ccf6d37c09d0eab"
        # Check for wsfull_object_hash
        hash_doc = _wait_for_doc('wsfull_object_hash', hsh)
        self.assertEqual(hash_doc['type'], 'MD5')
        # Check for wsfull_object_version
        ver_doc = _wait_for_doc('wsfull_object_version', '41347:5:1')
        self.assertEqual(ver_doc['workspace_id'], 41347)
        self.assertEqual(ver_doc['object_id'], 5)
        self.assertEqual(ver_doc['version'], 1)
        self.assertEqual(ver_doc['name'], "Narrative.1553621013004")
        self.assertEqual(ver_doc['hash'], "0e8d1a5090be7c4e9ccf6d37c09d0eab")
        self.assertEqual(ver_doc['size'], 26938)
        self.assertEqual(ver_doc['epoch'], 1554408999000)
        self.assertEqual(ver_doc['deleted'], False)
        # Check for wsfull_copied_from
        copy_edge = _wait_for_edge(
            'wsfull_copied_from',  # collection
            'wsfull_object_version/41347:5:1',  # from
            'wsfull_object_version/1:2:3'  # to
        )
        self.assertTrue(copy_edge)
        # Check for wsfull_version_of
        ver_edge = _wait_for_edge(
            'wsfull_version_of',  # collection
            'wsfull_object_version/41347:5:1',  # from
            'wsfull_object/41347:5'  # to
        )
        self.assertTrue(ver_edge)
        # Check for wsfull_ws_contains_obj
        contains_edge = _wait_for_edge(
            'wsfull_ws_contains_obj',  # collection
            'wsfull_workspace/41347',  # from
            'wsfull_object/41347:5'  # to
        )
        self.assertTrue(contains_edge)
        # Check for wsfull_obj_created_with_method edge
        created_with_edge = _wait_for_edge(
            'wsfull_obj_created_with_method',  # collection
            'wsfull_object_version/41347:5:1',
            'wsfull_method_version/narrative:3.10.0:UNKNOWN'
        )
        self.assertEqual(created_with_edge['method_params'], {})


def _produce(data, topic=_CONFIG['kafka_topics']['workspace_events']):
    producer = Producer({'bootstrap.servers': _CONFIG['kafka_server']})
    producer.produce(topic, json.dumps(data), callback=_delivery_report)
    producer.poll(60)


def _delivery_report(err, msg):
    if err is not None:
        print('Message delivery failed:', err)
    else:
        print('Message delivered to', msg.topic())


def _wait_for_edge(coll, from_key, to_key):
    """Fetch an edge with the RE API, waiting for it to become available with 30s timeout."""
    timeout = int(time.time()) + 30
    while True:
        results = get_edge(coll, from_key, to_key)
        if results['count'] > 0:
            break
        else:
            if int(time.time()) > timeout:
                raise RuntimeError('Timed out trying to fetch', from_key, to_key)
            time.sleep(1)
    return results['results'][0]


def _wait_for_doc(coll, key):
    """Fetch a doc with the RE API, waiting for it to become available with a 30s timeout."""
    timeout = int(time.time()) + 30
    while True:
        results = get_doc(coll, key)
        if results['count'] > 0:
            break
        else:
            if int(time.time()) > timeout:
                raise RuntimeError('Timed out trying to fetch', key)
            time.sleep(1)
    return results['results'][0]
