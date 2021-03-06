from __future__ import unicode_literals

from django.conf import settings
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.forms import Form
from django.forms.formsets import formset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.views.generic import View

from django_tables2 import RequestConfig

from .forms import BootstrapMixin, ConfirmationForm, CSVDataField
from .models import UserAction
from .paginators import EnhancedPaginator


class AddOrEditView(LoginRequiredMixin, View):
    model = None
    form = None
    return_url = None
    template = 'utils/object_add_edit.html'

    def get_object(self, kwargs):
        if 'asn' in kwargs:
            # Lookup object by ASN
            return get_object_or_404(self.model, asn=kwargs['asn'])

        if 'slug' in kwargs:
            # Lookup object by slug
            return get_object_or_404(self.model, slug=kwargs['slug'])

        if 'id' in kwargs:
            # Lookup object by ID
            return get_object_or_404(self.model, id=kwargs['id'])

        # New object
        return self.model()

    def alter_object(self, obj, request, args, kwargs):
        return obj

    def get_return_url(self, obj):
        if obj.pk:
            # If the object has an absolute URL, use it
            return obj.get_absolute_url()

        if self.return_url:
            # Otherwise use the default URL if given
            return reverse(self.return_url)

        # Or return to home
        return reverse('home')

    def get(self, request, *args, **kwargs):
        """
        Method used to render the view when form is not submitted.
        """
        obj = self.alter_object(self.get_object(kwargs), request, args, kwargs)
        form = self.form(instance=obj, initial=request.GET)

        return render(request, self.template, {
            'object': obj,
            'object_type': self.model._meta.verbose_name,
            'form': form,
            'return_url': self.get_return_url(obj),
        })

    def post(self, request, *args, **kwargs):
        """
        The form has been submitted, process it.
        """
        obj = self.get_object(kwargs)
        form = self.form(request.POST, instance=obj)

        if form.is_valid():
            # Check if the object will be created or modified
            created = not form.instance.pk

            # Save the object
            obj = form.save()

            # Notify user with a message
            message = 'Created ' if created else 'Modified '
            message = '{} {} {}'.format(
                message, self.model._meta.verbose_name, escape(obj))
            messages.success(request, mark_safe(message))

            # Log the action
            if created:
                UserAction.objects.log_create(request.user, obj, message)
            else:
                UserAction.objects.log_edit(request.user, obj, message)

            return redirect(self.get_return_url(obj))

        return render(request, self.template, {
            'object': obj,
            'object_type': self.model._meta.verbose_name,
            'form': form,
            'return_url': self.get_return_url(obj),
        })


class ConfirmationView(LoginRequiredMixin, View):
    return_url = None
    template = None

    def extra_context(self, kwargs):
        return {}

    def process(self, request, kwargs):
        pass

    def get(self, request, *args, **kwargs):
        form = ConfirmationForm(initial=request.GET)
        context = {
            'form': form,
        }
        context.update(self.extra_context(kwargs))

        return render(request, self.template, context)

    def post(self, request, *args, **kwargs):
        form = ConfirmationForm(request.POST)
        if form.is_valid():
            return self.process(request, kwargs)

        context = {
            'form': form,
        }
        context.update(self.extra_context(kwargs))

        return render(request, self.template, context)


class DeleteView(LoginRequiredMixin, View):
    model = None
    return_url = None
    template = 'utils/object_delete.html'

    def get_object(self, kwargs):
        if 'asn' in kwargs:
            # Lookup object by ASN
            return get_object_or_404(self.model, asn=kwargs['asn'])

        if 'slug' in kwargs:
            # Lookup object by slug
            return get_object_or_404(self.model, slug=kwargs['slug'])

        if 'id' in kwargs:
            # Lookup object by ID
            return get_object_or_404(self.model, id=kwargs['id'])

        return None

    def get_return_url(self, obj):
        if obj.pk:
            # If the object has an absolute URL, use it
            return obj.get_absolute_url()

        if self.return_url:
            # Otherwise use the default URL if given
            return reverse(self.return_url)

        # Or return to home
        return reverse('home')

    def get(self, request, *args, **kwargs):
        """
        Method used to render the view when form is not submitted.
        """
        obj = self.get_object(kwargs)
        form = ConfirmationForm(initial=request.GET)

        return render(request, self.template, {
            'object': obj,
            'form': form,
            'object_type': self.model._meta.verbose_name,
            'return_url': self.get_return_url(obj),
        })

    def post(self, request, *args, **kwargs):
        """
        The form has been submitted, process it.
        """
        obj = self.get_object(kwargs)
        form = ConfirmationForm(request.POST)

        if form.is_valid():
            obj.delete()

            # Notify the user
            message = 'Deleted {} {}'.format(
                self.model._meta.verbose_name, escape(obj))
            messages.success(request, message)

            # Log the action
            UserAction.objects.log_delete(request.user, obj, message)

            return redirect(self.get_return_url(obj))

        return render(request, self.template, {
            'object': obj,
            'form': form,
            'object_type': self.model._meta.verbose_name,
            'return_url': self.get_return_url(obj),
        })


class ImportView(LoginRequiredMixin, View):
    form_model = None
    return_url = None
    template = 'utils/object_import.html'

    def import_form(self, *args, **kwargs):
        fields = self.form_model().fields.keys()

        class ImportForm(BootstrapMixin, Form):
            csv = CSVDataField(fields=fields)

        return ImportForm(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        """
        Method used to render the view when form is not submitted.
        """
        return render(request, self.template, {
            'form': self.import_form(),
            'fields': self.form_model().fields,
            'obj_type': self.form_model._meta.model._meta.verbose_name,
            'return_url': self.return_url,
        })

    def post(self, request, *args, **kwargs):
        """
        The form has been submitted, process it.
        """
        new_objects = []
        form = self.import_form(request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    for row, data in enumerate(form.cleaned_data['csv'], start=1):
                        # Use a proper form for the given object/model
                        object_form = self.form_model(data)
                        if object_form.is_valid():
                            # Save the object
                            obj = object_form.save()
                            new_objects.append(obj)
                        else:
                            # Handle issues for each row
                            for field, err in object_form.errors.items():
                                form.add_error(
                                    'csv', "Row {} {}: {}".format(row, field, err[0]))
                            raise ValidationError('')

                if new_objects:
                    # Notify user of successful import
                    message = 'Imported {} {}'.format(
                        len(new_objects), new_objects[0]._meta.verbose_name_plural)
                    messages.success(request, message)

                    # Log the import action
                    UserAction.objects.log_import(request.user, ContentType.objects.get_for_model(
                        self.form_model._meta.model), message)

                    return redirect(self.return_url)
            except ValidationError:
                pass

        return render(request, self.template, {
            'form': form,
            'fields': self.form_model().fields,
            'object_type': self.form_model._meta.model._meta.verbose_name,
            'return_url': self.return_url,
        })


class ModelListView(View):
    queryset = None
    filter = None
    filter_form = None
    table = None
    template = None

    def build_queryset(self, request, kwargs):
        return self.queryset

    def alter_queryset(self, request):
        return self.queryset.all()

    def extra_context(self, kwargs):
        return {}

    def get(self, request, *args, **kwargs):
        # If no query set has been provided for some reasons
        if not self.queryset:
            self.queryset = self.build_queryset(request, kwargs)

        # If there is a filter, apply it
        if self.filter:
            self.queryset = self.filter(request.GET, self.queryset).qs

        # Alter the queryset if needed
        self.queryset = self.alter_queryset(request)

        # Build the table based on the queryset
        table = self.table(self.queryset)
        paginate = {
            'klass': EnhancedPaginator,
            'per_page': request.GET.get('per_page', settings.PAGINATE_COUNT)
        }
        RequestConfig(request, paginate).configure(table)

        # Set context and render
        context = {
            'table': table,
            'filter': self.filter,
            'filter_form': self.filter_form(request.GET, label_suffix='') if self.filter_form else None,
        }
        context.update(self.extra_context(kwargs))

        return render(request, self.template, context)


class TableImportView(LoginRequiredMixin, View):
    form_model = None
    return_url = None
    template = 'utils/table_import.html'

    def get_objects(self):
        return []

    def get_return_url(self):
        if self.return_url:
            # Use the default URL if given
            return reverse(self.return_url)

        # Or return to home
        return reverse('home')

    def get(self, request):
        """
        Method used to render the view when form is not submitted.
        """
        objects = self.get_objects()
        formset = None

        if len(objects) > 0:
            ObjectFormSet = formset_factory(self.form_model, extra=0)
            formset = ObjectFormSet(initial=objects)
        else:
            messages.info(request, 'No data to import.')
            return redirect(self.get_return_url())

        return render(request, self.template, {
            'formset': formset,
            'obj_type': self.form_model._meta.model._meta.verbose_name,
            'return_url': self.get_return_url(),
        })

    def post(self, request):
        """
        The form has been submitted, process it.
        """
        ObjectFormSet = formset_factory(self.form_model, extra=0)
        formset = ObjectFormSet(request.POST)
        new_objects = []

        if formset.is_valid():
            for form in formset:
                if form.is_valid():
                    instance = form.save()
                    new_objects.append(instance)

            if new_objects:
                # Notify user of successful import
                message = 'Imported {} {}'.format(
                    len(new_objects), new_objects[0]._meta.verbose_name_plural)
                messages.success(request, message)

                # Log the import action
                UserAction.objects.log_import(request.user, ContentType.objects.get_for_model(
                    self.form_model._meta.model), message)

            return redirect(self.get_return_url())

        formset = ObjectFormSet()
        return render(request, self.template, {
            'formset': formset,
            'obj_type': self.form_model._meta.model._meta.verbose_name,
            'return_url': self.get_return_url(),
        })
