from __future__ import unicode_literals

import json
import logging
import requests

from django.db import transaction
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.utils import timezone

from .models import Network, NetworkIXLAN, Prefix, Synchronization


NAMESPACES = {
    'facility': 'fac',
    'internet_exchange': 'ix',
    'internet_exchange_facility': 'ixfac',
    'internet_exchange_lan': 'ixlan',
    'internet_exchange_prefix': 'ixpfx',
    'network': 'net',
    'network_facility': 'netfac',
    'network_internet_exchange_lan': 'netixlan',
    'organization': 'org',
    'network_contact': 'poc',
}


class Object(object):
    """
    This is a class used to load JSON data into class fields for easier use.
    """

    def __init__(self, data):
        self.__dict__ = json.loads(json.dumps(data))

    def __str__(self):
        return str(self.__dict__)


class PeeringDB(object):
    """
    Class used to interact with the PeeringDB API.
    """
    logger = logging.getLogger('peering.manager.peeringdb')

    def lookup(self, namespace, search):
        """
        Sends a get request to the API given a namespace and some parameters.
        """
        # Enforce trailing slash and add namespace
        api_url = settings.PEERINGDB_API.strip('/') + '/' + namespace

        # Check if the depth param is provided, add it if not
        if 'depth' not in search:
            search['depth'] = 1

        # Make the request
        self.logger.debug('calling api: %s | %s', api_url, search)
        response = requests.get(api_url, params=search)

        return response.json() if response.status_code == 200 else None

    def record_last_sync(self, time, objects_changes):
        """
        Save the last synchronization details (number of objects and time) for
        later use (and logs).
        """
        number_of_changes = objects_changes['added'] + \
            objects_changes['updated'] + objects_changes['deleted']

        # Save the last sync time only if objects were retrieved
        if number_of_changes > 0:
            values = {
                'time': time,
                'added': objects_changes['added'],
                'updated': objects_changes['updated'],
                'deleted': objects_changes['deleted'],
            }

            last_sync = Synchronization(**values)
            last_sync.save()

            self.logger.debug('synchronizated %s objects at %s',
                              number_of_changes, last_sync.time)

    def get_last_sync_time(self):
        """
        Return the last time of synchronization based on the latest record.
        The time is returned as an integer UNIX timestamp.
        """
        # Assume first sync
        last_sync_time = 0
        try:
            # If a sync has already been performed, get the last of it given
            # its time
            last_sync = Synchronization.objects.latest('time')
            last_sync_time = last_sync.time.timestamp()
        except Synchronization.DoesNotExist:
            pass

        return int(last_sync_time)

    def synchronize_objects(self, last_sync, namespace, model):
        """
        Synchronizes all the objects of a namespace of the PeeringDB to the
        local database. This function is meant to be run regularly to update
        the local database with the latest changes.

        If the object already exists locally it will be updated and no new
        entry will be created.

        If the object is marked as deleted in the PeeringDB, it will be locally
        deleted.

        This function returns the number of objects that have been successfully
        synchronized to the local database.
        """
        objects_added = 0
        objects_updated = 0
        objects_deleted = 0

        # Get all network changes since the last sync
        search = {'since': last_sync, 'depth': 0}
        result = self.lookup(namespace, search)

        if not result:
            return None

        for data in result['data']:
            peeringdb_object = Object(data)
            marked_as_deleted = peeringdb_object.status == 'deleted'
            marked_as_new = False

            try:
                # Get the local object by its ID
                local_object = model.objects.get(pk=peeringdb_object.id)

                # Object marked as deleted so remove it locally too
                if marked_as_deleted:
                    local_object.delete()
                    objects_deleted += 1
                    self.logger.debug('deleted %s #%s from local database',
                                      model._meta.verbose_name.lower(), peeringdb_object.id)
                    continue
            except model.DoesNotExist:
                # Local object does not exist so create it
                local_object = model()
                marked_as_new = True

            # Set the value for each field
            for model_field in model._meta.get_fields():
                field_name = model_field.name
                value = getattr(peeringdb_object, field_name)

                try:
                    field = local_object._meta.get_field(field_name)
                except FieldDoesNotExist:
                    field = None
                    self.logger.error(
                        'bug found? field: %s for model: %s', field_name, model._meta.verbose_name.lower())

                if field:
                    setattr(local_object, field_name, value)

            try:
                local_object.full_clean()
            except ValidationError:
                self.logger.error('bug found? error while validating id: %s for model: %s',
                                  peeringdb_object.id, model._meta.verbose_name.lower())
                continue

            # Save the local object
            local_object.save()

            # Update counters
            if marked_as_new:
                objects_added += 1
                self.logger.debug(
                    'created %s #%s from peeringdb', model._meta.verbose_name.lower(), local_object.id)
            else:
                objects_updated += 1
                self.logger.debug(
                    'updated %s #%s from peeringdb', model._meta.verbose_name.lower(), local_object.id)

        return (objects_added, objects_updated, objects_deleted)

    def update_local_database(self, last_sync):
        # Set time of sync
        time_of_sync = timezone.now()
        objects_to_sync = [
            (NAMESPACES['network'], Network),
            (NAMESPACES['network_internet_exchange_lan'], NetworkIXLAN),
            (NAMESPACES['internet_exchange_prefix'], Prefix),
        ]
        list_of_changes = []

        # Make a single transaction, avoid too much database commits (poor
        # speed) and fail the whole synchronization if something goes wrong
        with transaction.atomic():
            # Try to sync objects
            for (namespace, object_type) in objects_to_sync:
                changes = self.synchronize_objects(
                    last_sync, namespace, object_type)
                list_of_changes.append(changes)

        objects_changes = {
            'added': sum(added for added, _, _ in list_of_changes),
            'updated': sum(updated for _, updated, _ in list_of_changes),
            'deleted': sum(deleted for _, _, deleted in list_of_changes),
        }

        # Save the last sync time
        self.record_last_sync(time_of_sync, objects_changes)

    def get_autonomous_system(self, asn):
        """
        Return an AS (and its details) given its ASN. The result can come from
        the local database (cache built with the peeringdb_sync command). If
        the AS details are not found in the local database, they will be
        fetched online which will take more time.
        """
        try:
            # Try to get from cached data
            network = Network.objects.get(asn=asn)
        except Network.DoesNotExist:
            # If no cached data found, query the API
            search = {'asn': asn}
            result = self.lookup(NAMESPACES['network'], search)

            if not result:
                return None

            network = Object(result['data'][0])

        return network

    def get_ix_network(self, ix_network_id):
        """
        Return an IX networks (and its details) given its ID. The result can
        come from the local database (cache built with the peeringdb_sync
        command). If the IX network is not found in the local database, it will
        be fetched online which will take more time.
        """
        try:
            # Try to get from cached data
            network_ixlan = NetworkIXLAN.objects.get(id=ix_network_id)
        except NetworkIXLAN.DoesNotExist:
            # If no cached data found, query the API
            search = {'id': ix_network_id}
            result = self.lookup(
                NAMESPACES['network_internet_exchange_lan'], search)

            if not result:
                return None

            network_ixlan = Object(result['data'][0])

        return network_ixlan

    def get_ix_networks_for_asn(self, asn):
        """
        Returns a list of all IX networks an AS is connected to.
        """
        # Try to get from cached data
        network_ixlans = NetworkIXLAN.objects.filter(asn=asn)

        # If nothing found in cache, try to fetch data online
        if not network_ixlans:
            search = {'asn': asn}
            result = self.lookup(
                NAMESPACES['network_internet_exchange_lan'], search)

            if not result:
                return None

            network_ixlans = []
            for ix_network in result['data']:
                network_ixlans.append(Object(ix_network))

        return network_ixlans

    def get_prefixes_for_ix_network(self, ix_network_id):
        """
        Returns a list of all prefixes used by an IX network.
        """
        prefixes = []

        # Get the NetworkIXLAN object using its ID
        network_ixlan = self.get_ix_network(ix_network_id)

        if network_ixlan:
            # Try to get prefixes from cache
            ix_prefixes = Prefix.objects.filter(
                ixlan_id=network_ixlan.ixlan_id)

            # If not cached data, try to fetch online
            if not ix_prefixes:
                search = {'ixlan_id': network_ixlan.ixlan_id}
                result = self.lookup(
                    NAMESPACES['internet_exchange_prefix'], search)

                if not result:
                    return prefixes

                ix_prefixes = []
                for ix_prefix in result['data']:
                    ix_prefixes.append(Object(ix_prefix))

            # Build a list with protocol and prefix couples
            for ix_prefix in ix_prefixes:
                prefixes.append({
                    'protocol': ix_prefix.protocol,
                    'prefix': ix_prefix.prefix,
                })

        return prefixes

    def get_peers_for_ix(self, ix_id):
        """
        Returns a dict with details for peers for the IX corresponding to the
        given ID. This function try to leverage the use of local database
        caching. If the cache is not built it can take some time to execute due
        to the amount of peers on the IX which increases the number of API
        calls to be made.
        """
        # Try to get from cached data
        network_ixlans = NetworkIXLAN.objects.filter(ix_id=ix_id)

        # If nothing found in cache, try to fetch data online
        if not network_ixlans:
            search = {'ix_id': ix_id}
            result = self.lookup(
                NAMESPACES['network_internet_exchange_lan'], search)

            if not result:
                return None

            network_ixlans = []
            for data in result['data']:
                network_ixlans.append(Object(data))

        # List potential peers
        peers = []
        for network_ixlan in network_ixlans:
            # Ignore our own ASN
            if network_ixlan.asn == settings.MY_ASN:
                continue

            # Get more details about the current network
            network = self.get_autonomous_system(network_ixlan.asn)

            # Package all gathered details
            peers.append({
                'network': network,
                'network_ixlan': network_ixlan,
            })

        return peers
