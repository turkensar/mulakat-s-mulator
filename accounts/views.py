from django.contrib.auth import login
from django.shortcuts import redirect, render
from django_ratelimit.decorators import ratelimit

from .forms import RegisterForm


@ratelimit(key='ip', rate='5/h', method='POST', block=False)
def register(request):
    if request.user.is_authenticated:
        return redirect('panel')

    if request.method == 'POST':
        if getattr(request, 'limited', False):
            form = RegisterForm(request.POST)
            form.add_error(
                None, 'Çok fazla kayıt denemesi yapıldı. Lütfen bir süre sonra tekrar dene.'
            )
        else:
            form = RegisterForm(request.POST)
            if form.is_valid():
                user = form.save()
                login(request, user)
                return redirect('panel')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})
