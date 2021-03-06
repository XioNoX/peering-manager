"""
Django settings for peering_manager project.

Generated by 'django-admin startproject' using Django 1.11.4.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.11/ref/settings/
"""

import os
import socket

from django.contrib.messages import constants as messages
from django.core.exceptions import ImproperlyConfigured

try:
    from peering_manager import configuration
except ImportError:
    raise ImproperlyConfigured(
        'Configuration file is not present. Please define peering_manager/configuration.py per the documentation.')

VERSION = '0.99-dev'

SECRET_KEY = getattr(configuration, 'SECRET_KEY', '')
ALLOWED_HOSTS = getattr(configuration, 'ALLOWED_HOSTS', [])
BASE_PATH = getattr(configuration, 'BASE_PATH', '')
if BASE_PATH:
    BASE_PATH = BASE_PATH.strip('/') + '/'  # Enforce trailing slash only
DEBUG = getattr(configuration, 'DEBUG', False)
NAPALM_USERNAME = getattr(configuration, 'NAPALM_USERNAME', '')
NAPALM_PASSWORD = getattr(configuration, 'NAPALM_PASSWORD', '')
NAPALM_TIMEOUT = getattr(configuration, 'NAPALM_TIMEOUT', 30)
NAPALM_ARGS = getattr(configuration, 'NAPALM_ARGS', {})
PAGINATE_COUNT = getattr(configuration, 'PAGINATE_COUNT', 20)
TIME_ZONE = getattr(configuration, 'TIME_ZONE', 'UTC')
MY_ASN = getattr(configuration, 'MY_ASN', -1)

if MY_ASN == -1:
    raise ImproperlyConfigured(
        'The MY_ASN setting must be set to a valid AS number.')

# PeeringDB URLs
PEERINGDB_API = 'https://peeringdb.com/api/'
PEERINGDB = 'https://peeringdb.com/asn/'

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


try:
    from peering_manager.ldap_config import *
    LDAP_CONFIGURED = True
except ImportError:
    LDAP_CONFIGURED = False

# If LDAP is configured, load the config
if LDAP_CONFIGURED:
    try:
        import ldap
        import django_auth_ldap

        # Prepend LDAPBackend to the default ModelBackend
        AUTHENTICATION_BACKENDS = [
            'django_auth_ldap.backend.LDAPBackend',
            'django.contrib.auth.backends.ModelBackend',
        ]
    except ImportError:
        raise ImproperlyConfigured(
            'LDAP authentication has been configured, but django-auth-ldap is not installed. You can remove peering_manager/ldap_config.py to disable LDAP.'
        )


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_filters',
    'django_tables2',
    'peering',
    'peeringdb',
    'utils',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'peering_manager.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR + '/templates/'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'utils.context_processors.settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'peering_manager.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Django logging
LOGGING = {
    'version': 1,
    'formatters': {
        'simple': {
            'format': '%(asctime)s | %(levelname)s | %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': 'logs/peering-manager.log',
            'when': 'midnight',
            'interval': 1,
            'backupCount': 5,
            'formatter': 'simple',
        }
    },
    'loggers': {
        'peering.manager.peeringdb': {
            'handlers': ['file'],
            'level': 'DEBUG',
        }
    }
}


# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/
LANGUAGE_CODE = 'en-us'
USE_I18N = True
USE_L10N = True
USE_TZ = True


# Authentication URL
LOGIN_URL = '/{}login/'.format(BASE_PATH)


# Messages
MESSAGE_TAGS = {
    messages.ERROR: 'danger',
}


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/
STATIC_ROOT = BASE_DIR + '/static/'
STATIC_URL = '/{}static/'.format(BASE_PATH)
STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'project-static'),
)

# Django filters
FILTERS_NULL_CHOICE_LABEL = 'None'
FILTERS_NULL_CHOICE_VALUE = '0'

try:
    HOSTNAME = socket.gethostname()
except:
    HOSTNAME = 'localhost'
