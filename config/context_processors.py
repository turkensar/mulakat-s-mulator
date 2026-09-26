from django.conf import settings


def google_client_id(request):
    return {'GOOGLE_CLIENT_ID': settings.GOOGLE_CLIENT_ID}


def contact_email(request):
    return {'CONTACT_EMAIL': settings.CONTACT_EMAIL}
