
from app_state import state, on

@on('state.countries')
def countries():
    print(f'countries changed to: {state.countries}')
    
@on('state.countries.Australia.population')
def au_population():
    population = state.get('countries', {}).get('Australia', {}).get('population')
    print(f'Australia population now: {population}')
    
state.countries = {'Australia': {'code': 'AU'}, 'Brazil': {}}
state.countries.Australia.population = 4500000 
