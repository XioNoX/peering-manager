from __future__ import unicode_literals

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import slugify
from django.utils.html import escape
from django.views.generic import View

from django_tables2 import RequestConfig

import json

from .filters import (AutonomousSystemFilter, CommunityFilter, ConfigurationTemplateFilter,
                      InternetExchangeFilter, PeeringSessionFilter, RouterFilter)
from .forms import (AutonomousSystemForm, AutonomousSystemCSVForm, AutonomousSystemFilterForm, CommunityForm, CommunityCSVForm, CommunityFilterForm, ConfigurationTemplateForm, ConfigurationTemplateFilterForm, InternetExchangeForm,
                    InternetExchangePeeringDBForm, InternetExchangeCommunityForm, InternetExchangeCSVForm, InternetExchangeFilterForm, PeeringSessionForm, PeeringSessionFilterForm, PeeringSessionFilterFormForAS, RouterForm, RouterCSVForm, RouterFilterForm)
from .models import (AutonomousSystem, Community,
                     ConfigurationTemplate, InternetExchange, PeeringSession, Router)
from .tables import (AutonomousSystemTable, CommunityTable, ConfigurationTemplateTable,
                     InternetExchangeTable, PeerTable, PeeringSessionTable, PeeringSessionTableForAS, RouterTable)
from peeringdb.api import PeeringDB
from peeringdb.models import Network, NetworkIXLAN
from utils.forms import ConfirmationForm
from utils.models import UserAction
from utils.paginators import EnhancedPaginator
from utils.views import (AddOrEditView, ConfirmationView,
                         DeleteView, ImportView, ModelListView, TableImportView)


class ASList(ModelListView):
    queryset = AutonomousSystem.objects.order_by('asn')
    filter = AutonomousSystemFilter
    filter_form = AutonomousSystemFilterForm
    table = AutonomousSystemTable
    template = 'peering/as/list.html'


class ASAdd(AddOrEditView):
    model = AutonomousSystem
    form = AutonomousSystemForm
    return_url = 'peering:as_list'
    template = 'peering/as/add_edit.html'


class ASImport(ImportView):
    form_model = AutonomousSystemCSVForm
    return_url = 'peering:as_list'


class ASDetails(View):
    def get(self, request, asn):
        autonomous_system = get_object_or_404(AutonomousSystem, asn=asn)
        context = {
            'autonomous_system': autonomous_system,
        }
        return render(request, 'peering/as/details.html', context)


class ASEdit(AddOrEditView):
    model = AutonomousSystem
    form = AutonomousSystemForm
    template = 'peering/as/add_edit.html'


class ASDelete(DeleteView):
    model = AutonomousSystem
    return_url = 'peering:as_list'


class ASPeeringDBSync(View):
    def get(self, request, asn):
        autonomous_system = get_object_or_404(AutonomousSystem, asn=asn)
        synced = autonomous_system.sync_with_peeringdb()

        if not synced:
            messages.error(
                request, 'Unable to synchronize AS details with PeeringDB.')
        else:
            messages.success(
                request, 'AS details have been synchronized with PeeringDB.')

        return redirect(autonomous_system.get_absolute_url())


class ASPeeringSessions(ModelListView):
    filter = PeeringSessionFilter
    filter_form = PeeringSessionFilterFormForAS
    table = PeeringSessionTableForAS
    template = 'peering/as/sessions.html'

    def build_queryset(self, request, kwargs):
        queryset = None
        # The queryset needs to be composed of PeeringSession objects but they
        # are linked to an AS. So first of all we need to retrieve the AS for
        # which we want to get the peering sessions.
        if 'asn' in kwargs:
            autonomous_system = get_object_or_404(
                AutonomousSystem, asn=kwargs['asn'])
            queryset = autonomous_system.peeringsession_set.order_by(
                'internet_exchange', 'ip_address')

        return queryset

    def extra_context(self, kwargs):
        extra_context = {}

        # Since we are in the context of an AS we need to keep the reference
        # for it
        if 'asn' in kwargs:
            autonomous_system = get_object_or_404(
                AutonomousSystem, asn=kwargs['asn'])
            extra_context.update({'autonomous_system': autonomous_system})

        return extra_context


class CommunityList(ModelListView):
    queryset = Community.objects.all()
    filter = CommunityFilter
    filter_form = CommunityFilterForm
    table = CommunityTable
    template = 'peering/community/list.html'


class CommunityAdd(AddOrEditView):
    model = Community
    form = CommunityForm
    return_url = 'peering:community_list'
    template = 'peering/community/add_edit.html'


class CommunityImport(ImportView):
    form_model = CommunityCSVForm
    return_url = 'peering:community_list'


class CommunityDetails(View):
    def get(self, request, id):
        community = get_object_or_404(Community, id=id)
        context = {
            'community': community,
        }
        return render(request, 'peering/community/details.html', context)


class CommunityEdit(AddOrEditView):
    model = Community
    form = CommunityForm
    template = 'peering/community/add_edit.html'


class CommunityDelete(DeleteView):
    model = Community
    return_url = 'peering:community_list'


class ConfigTemplateList(ModelListView):
    queryset = ConfigurationTemplate.objects.all()
    filter = ConfigurationTemplateFilter
    filter_form = ConfigurationTemplateFilterForm
    table = ConfigurationTemplateTable
    template = 'peering/config/list.html'


class ConfigTemplateAdd(AddOrEditView):
    model = ConfigurationTemplate
    form = ConfigurationTemplateForm
    return_url = 'peering:configuration_template_list'


class ConfigTemplateDetails(View):
    def get(self, request, id):
        configuration_template = get_object_or_404(
            ConfigurationTemplate, id=id)
        internet_exchanges = InternetExchange.objects.filter(
            configuration_template=configuration_template)
        context = {
            'configuration_template': configuration_template,
            'internet_exchanges': internet_exchanges,
        }
        return render(request, 'peering/config/details.html', context)


class ConfigTemplateEdit(AddOrEditView):
    model = ConfigurationTemplate
    form = ConfigurationTemplateForm


class ConfigTemplateDelete(DeleteView):
    model = ConfigurationTemplate
    return_url = 'peering:configuration_template_list'


class IXList(ModelListView):
    queryset = InternetExchange.objects.order_by('name')
    table = InternetExchangeTable
    filter = InternetExchangeFilter
    filter_form = InternetExchangeFilterForm
    template = 'peering/ix/list.html'


class IXAdd(AddOrEditView):
    model = InternetExchange
    form = InternetExchangeForm
    return_url = 'peering:ix_list'
    template = 'peering/ix/add_edit.html'


class IXImport(ImportView):
    form_model = InternetExchangeCSVForm
    return_url = 'peering:ix_list'


class IXImportFromRouter(ConfirmationView):
    template = 'peering/ix/import_from_router.html'

    def extra_context(self, kwargs):
        if 'slug' in kwargs:
            internet_exchange = get_object_or_404(
                InternetExchange, slug=kwargs['slug'])
            return {'internet_exchange': internet_exchange}
        return {}

    def process(self, request, kwargs):
        internet_exchange = get_object_or_404(
            InternetExchange, slug=kwargs['slug'])
        result = internet_exchange.import_peering_sessions_from_router()

        # Set the return URL
        self.return_url = internet_exchange.get_peering_sessions_list_url()

        if not result:
            messages.error(
                request, 'Cannot import peering sessions from the router.')
        else:
            if result[0] == 0 and result[1] == 0:
                messages.warning(
                    request, 'No peering sessions have been imported.')
            else:
                if result[0] > 0:
                    message = 'Imported {} {}'.format(
                        result[0], AutonomousSystem._meta.verbose_name_plural)
                    messages.success(message)
                    UserAction.objects.log_import(
                        request.user, AutonomousSystem, message)

                if result[1] > 0:
                    message = 'Imported {} {}'.format(
                        result[0], PeeringSession._meta.verbose_name_plural)
                    messages.success(message)
                    UserAction.objects.log_import(
                        request.user, PeeringSession, message)

        return redirect(self.return_url)


class IXPeeringDBImport(TableImportView):
    form_model = InternetExchangePeeringDBForm
    return_url = 'peering:ix_list'

    def get_objects(self):
        objects = []
        known_objects = []
        api = PeeringDB()

        for ix in InternetExchange.objects.all():
            if ix.peeringdb_id:
                known_objects.append(ix.peeringdb_id)

        ix_networks = api.get_ix_networks_for_asn(settings.MY_ASN)
        for ix_network in ix_networks:
            if ix_network.id not in known_objects:
                objects.append({
                    'peeringdb_id': ix_network.id,
                    'name': ix_network.name,
                    'slug': slugify(ix_network.name),
                    'ipv6_address': ix_network.ipaddr6,
                    'ipv4_address': ix_network.ipaddr4,
                })

        return objects


class IXDetails(View):
    def get(self, request, slug):
        internet_exchange = get_object_or_404(InternetExchange, slug=slug)
        context = {
            'internet_exchange': internet_exchange,
        }
        return render(request, 'peering/ix/details.html', context)


class IXEdit(AddOrEditView):
    model = InternetExchange
    form = InternetExchangeForm
    template = 'peering/ix/add_edit.html'


class IXDelete(DeleteView):
    model = InternetExchange
    return_url = 'peering:ix_list'


class IXUpdateCommunities(AddOrEditView):
    model = InternetExchange
    form = InternetExchangeCommunityForm
    template = 'peering/ix/communities.html'

    def get(self, request, *args, **kwargs):
        obj = self.alter_object(self.get_object(kwargs), request, args, kwargs)
        form = self.form(instance=obj)

        return render(request, self.template, {
            'object': obj,
            'object_type': self.model._meta.verbose_name,
            'form': form,
            'return_url': self.get_return_url(obj),
        })

    def post(self, request, *args, **kwargs):
        obj = self.get_object(kwargs)
        form = self.form(request.POST, instance=obj)

        if form.is_valid():
            # Clear communities to avoid duplicates
            obj.communities.clear()
            # Add communities one by one
            for community in request.POST.getlist('communities'):
                obj.communities.add(community)
            # Save the object and its linked communities
            obj.save()

            return redirect(self.get_return_url(obj))

        return render(request, self.template, {
            'object': obj,
            'object_type': self.model._meta.verbose_name,
            'form': form,
            'return_url': self.get_return_url(obj),
        })


class IXPeeringSessions(ModelListView):
    filter = PeeringSessionFilter
    filter_form = PeeringSessionFilterForm
    table = PeeringSessionTable
    template = 'peering/ix/sessions.html'

    def build_queryset(self, request, kwargs):
        queryset = None
        # The queryset needs to be composed of PeeringSession objects but they
        # are linked to an IX. So first of all we need to retrieve the IX on
        # which we want to get the peering sessions.
        if 'slug' in kwargs:
            internet_exchange = get_object_or_404(
                InternetExchange, slug=kwargs['slug'])
            queryset = internet_exchange.peeringsession_set.order_by(
                'autonomous_system.asn', 'ip_address')

        return queryset

    def extra_context(self, kwargs):
        extra_context = {}

        # Since we are in the context of an IX we need to keep the reference
        # for it
        if 'slug' in kwargs:
            internet_exchange = get_object_or_404(
                InternetExchange, slug=kwargs['slug'])
            extra_context.update({'internet_exchange': internet_exchange})

        return extra_context


class IXPeers(LoginRequiredMixin, View):
    def get(self, request, slug):
        internet_exchange = get_object_or_404(InternetExchange, slug=slug)
        available_peers = PeerTable(internet_exchange.get_available_peers())
        paginate = {
            'klass': EnhancedPaginator,
            'per_page': settings.PAGINATE_COUNT
        }
        RequestConfig(request, paginate=paginate).configure(available_peers)

        context = {
            'internet_exchange': internet_exchange,
            'available_peers': available_peers,
        }

        return render(request, 'peering/ix/peers.html', context)


class IXAddPeer(LoginRequiredMixin, View):
    def get(self, request, slug, network_id, network_ixlan_id):
        # Get required objects or fail if some are missing
        internet_exchange = get_object_or_404(InternetExchange, slug=slug)
        network = get_object_or_404(Network, id=network_id)
        network_ixlan = get_object_or_404(NetworkIXLAN, id=network_ixlan_id)

        # Check if the AS we are going to peer with is already known
        known_autonomous_system = True
        try:
            AutonomousSystem.objects.get(asn=network.asn)
        except AutonomousSystem.DoesNotExist:
            known_autonomous_system = False

        # Init a form that the user must submit to confirm the peering
        form = ConfirmationForm(initial=request.GET)

        context = {
            'internet_exchange': internet_exchange,
            'known_autonomous_system': known_autonomous_system,
            'network': network,
            'network_ixlan': network_ixlan,
            'form': form,
            'return_url': internet_exchange.get_peer_list_url(),
        }
        return render(request, 'peering/ix/add_peer.html', context)

    def post(self, request, slug, network_id, network_ixlan_id):
        # Get required objects or fail if some are missing
        internet_exchange = get_object_or_404(InternetExchange, slug=slug)
        network = get_object_or_404(Network, id=network_id)
        network_ixlan = get_object_or_404(NetworkIXLAN, id=network_ixlan_id)

        # Init the form that the user must have submitted
        form = ConfirmationForm(request.POST)
        if form.is_valid():
            peer_added = False

            with transaction.atomic():
                # Create the new AS if needed
                try:
                    autonomous_system = AutonomousSystem.objects.get(
                        asn=network.asn)
                except AutonomousSystem.DoesNotExist:
                    values = {
                        'asn': network.asn,
                        'name': network.name,
                        'irr_as_set': network.irr_as_set,
                        'ipv6_max_prefixes': network.info_prefixes6,
                        'ipv4_max_prefixes': network.info_prefixes4,
                    }
                    autonomous_system = AutonomousSystem(**values)
                    autonomous_system.save()
                    peer_added = True
                    # Log the action
                    UserAction.objects.log_create(request.user, autonomous_system, 'Created {} {}'.format(
                        AutonomousSystem._meta.verbose_name, escape(autonomous_system)))

                # Record the IPv6 session if we can
                if network_ixlan.ipaddr6:
                    try:
                        PeeringSession.objects.get(
                            autonomous_system=autonomous_system, internet_exchange=internet_exchange, ip_address=network_ixlan.ipaddr6)
                    except PeeringSession.DoesNotExist:
                        values = {
                            'autonomous_system': autonomous_system,
                            'internet_exchange': internet_exchange,
                            'ip_address': network_ixlan.ipaddr6,
                        }
                        session = PeeringSession(**values)
                        session.save()
                        peer_added = True
                        # Log the action
                        UserAction.objects.log_create(request.user, session, 'Created {} {}'.format(
                            PeeringSession._meta.verbose_name, escape(session)))

                # Record the IPv4 session if we can
                if network_ixlan.ipaddr4:
                    try:
                        PeeringSession.objects.get(
                            autonomous_system=autonomous_system, internet_exchange=internet_exchange, ip_address=network_ixlan.ipaddr4)
                    except PeeringSession.DoesNotExist:
                        values = {
                            'autonomous_system': autonomous_system,
                            'internet_exchange': internet_exchange,
                            'ip_address': network_ixlan.ipaddr4,
                        }
                        session = PeeringSession(**values)
                        session.save()
                        peer_added = True
                        # Log the action
                        UserAction.objects.log_create(request.user, session, 'Created {} {}'.format(
                            PeeringSession._meta.verbose_name, escape(session)))

                # Notify the user
                if peer_added:
                    messages.success(request, '{} peer successfully added on {}.'.format(
                        autonomous_system, internet_exchange))

            return redirect(internet_exchange.get_absolute_url())

        context = {
            'internet_exchange': internet_exchange,
            'known_autonomous_system': False,
            'network': network,
            'network_ixlan': network_ixlan,
            'form': form,
            'return_url': internet_exchange.get_peer_list_url(),
        }
        return render(request, 'peering/ix/add_peer.html', context)


class IXConfig(LoginRequiredMixin, View):
    def get(self, request, slug):
        internet_exchange = get_object_or_404(InternetExchange, slug=slug)

        context = {
            'internet_exchange': internet_exchange,
            'internet_exchange_configuration': internet_exchange.get_config(),
        }

        return render(request, 'peering/ix/configuration.html', context)


class PeeringSessionAdd(AddOrEditView):
    model = PeeringSession
    form = PeeringSessionForm
    template = 'peering/session/add_edit.html'

    def get_object(self, kwargs):
        if 'id' in kwargs:
            return get_object_or_404(self.model, id=kwargs['id'])

        return self.model()

    def alter_object(self, obj, request, args, kwargs):
        if 'slug' in kwargs:
            obj.internet_exchange = get_object_or_404(
                InternetExchange, slug=kwargs['slug'])

        return obj

    def get_return_url(self, obj):
        return obj.internet_exchange.get_absolute_url()


class PeeringSessionDetails(View):
    def get(self, request, id):
        peering_session = get_object_or_404(PeeringSession, id=id)
        context = {'peering_session': peering_session}
        return render(request, 'peering/session/details.html', context)


class PeeringSessionEdit(AddOrEditView):
    model = PeeringSession
    form = PeeringSessionForm
    template = 'peering/session/add_edit.html'


class PeeringSessionDelete(DeleteView):
    model = PeeringSession

    def get_return_url(self, obj):
        return obj.internet_exchange.get_absolute_url()


class RouterList(ModelListView):
    queryset = Router.objects.all()
    filter = RouterFilter
    filter_form = RouterFilterForm
    table = RouterTable
    template = 'peering/router/list.html'


class RouterAdd(AddOrEditView):
    model = Router
    form = RouterForm
    return_url = 'peering:router_list'
    template = 'peering/router/add_edit.html'


class RouterImport(ImportView):
    form_model = RouterCSVForm
    return_url = 'peering:router_list'


class RouterDetails(View):
    def get(self, request, id):
        router = get_object_or_404(Router, id=id)
        internet_exchanges = InternetExchange.objects.filter(router=router)
        context = {
            'router': router,
            'internet_exchanges': internet_exchanges,
        }
        return render(request, 'peering/router/details.html', context)


class RouterEdit(AddOrEditView):
    model = Router
    form = RouterForm
    template = 'peering/router/add_edit.html'


class RouterDelete(DeleteView):
    model = Router
    return_url = 'peering:router_list'


class AsyncRouterPing(View):
    def get(self, request, router_id):
        router = get_object_or_404(Router, id=router_id)

        return HttpResponse(json.dumps({
            'status': 'success' if router.test_napalm_connection() else 'error',
        }))


class AsyncRouterDiff(View):
    def get(self, request, slug):
        internet_exchange = get_object_or_404(InternetExchange, slug=slug)
        changes = internet_exchange.router.set_configuration(
            internet_exchange.get_config(), False)

        return HttpResponse(json.dumps({
            'changed': True if changes else False,
            'changes': changes,
        }))


class AsyncRouterSave(View):
    def get(self, request, slug):
        internet_exchange = get_object_or_404(InternetExchange, slug=slug)
        changes = internet_exchange.router.set_configuration(
            internet_exchange.get_config(), True)

        return HttpResponse(json.dumps({
            'success': True if changes else False,
        }))
