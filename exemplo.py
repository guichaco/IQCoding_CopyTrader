from iqoptionapi.stable_api import IQ_Option
import time, json, logging, configparser
from datetime import datetime, date, timedelta
from dateutil import tz


logging.disable(level=(logging.DEBUG))

API = IQ_Option('login', 'senha')
API.connect()

API.change_balance('PRACTICE') # PRACTICE / REAL

while True:
	if API.check_connect() == False:
		print('Erro ao se conectar')
		
		API.connect()
	else:
		print('\n\nConectado com sucesso')
		break
	
	time.sleep(1)

def perfil():
	perfil = json.loads(json.dumps(API.get_profile_ansyc()))
	
	return perfil
	
	'''
		name
		first_name
		last_name
		email
		city
		nickname
		currency
		currency_char 
		address
		created
		postal_index
		gender
		birthdate
		balance		
	'''

def timestamp_converter(x):
	hora = datetime.strptime(datetime.utcfromtimestamp(x).strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
	hora = hora.replace(tzinfo=tz.gettz('GMT'))
	
	return str(hora.astimezone(tz.gettz('America/Sao Paulo')))[:-6]

def banca():
	return API.get_balance()

def payout(par, tipo, timeframe = 1):
	if tipo == 'turbo':
		a = API.get_all_profit()
		return int(100 * a[par]['turbo'])
		
	elif tipo == 'digital':
	
		API.subscribe_strike_list(par, timeframe)
		while True:
			d = API.get_digital_current_profit(par, timeframe)
			if d != False:
				d = int(d)
				break
			time.sleep(1)
		API.unsubscribe_strike_list(par, timeframe)
		return d

def configuracao():
	arquivo = configparser.RawConfigParser()
	arquivo.read('config.txt')	
		
	return {'martingale': arquivo.get('GERAL', 'martingale'), 'sorosgale': arquivo.get('GERAL', 'sorosgale'), 'niveis': arquivo.get('GERAL', 'niveis'), 'filtro_pais': arquivo.get('GERAL', 'filtro_pais'), 'filtro_top_traders': arquivo.get('GERAL', 'filtro_top_traders'), 'valor_minimo': arquivo.get('GERAL', 'valor_minimo'), 'paridade': arquivo.get('GERAL', 'paridade'), 'valor_entrada': arquivo.get('GERAL', 'valor_entrada'), 'timeframe': arquivo.get('GERAL', 'timeframe')}

def martingale(tipo, valor, payout):
	if tipo == 'simples':
		return valor * 2.2
	else:
	
		lucro_esperado = float(valor) * float(payout)
		perca = valor
		while True:
			if round(float(valor) * float(payout), 2) > round(float(abs(perca)) + float(lucro_esperado), 2):
				return round(valor, 2)
				break
			valor += 0.01
	
def entradas(par, entrada, direcao, timeframe):
	status,id = API.buy_digital_spot(par, entrada, direcao, timeframe)

	if status:
		while True:
			status,lucro = API.check_win_digital_v2(id)
			
			if status:
				if lucro > 0:
					return 'win',round(lucro, 2)
				else:
					return 'loss',0
				break
	else:
		return 'error',0

# Carrega as configuracoes
config = configuracao()

# Filtros
# 1º Filtro por valor da entrada copiada
# 2º Filtro para copiar entrada dos top X 
# 3º Filtro Pais

# Captura os dados necessarios do ranking
def filtro_ranking(config):
	
	user_id = []
	
	try:
		ranking = API.get_leader_board('Worldwide' if config['filtro_pais'] == 'todos' else config['filtro_pais'].upper() , 1, int(config['filtro_top_traders']), 0)
	
		if int(config['filtro_top_traders']) != 0:
			for n in ranking['result']['positional']:
				id = ranking['result']['positional'][n]['user_id']
				user_id.append(id)
				
				'''
				perfil_info = API.get_user_profile_client(id)
				if perfil_info['status'] == 'online':
					op = API.get_users_availability(id)
					
					try:			
						tipo = op['statuses'][0]['selected_instrument_type']
						par = API.get_name_by_activeId(op['statuses'][0]['selected_asset_id']).replace('/', '')
						
						print('\n [',n,'] ',perfil_info['user_name'])		
						print(tipo)			
						print(par)
						
						
					except:
						pass
				'''
				
	except:
		pass
		
	return user_id


filtro_top_traders = filtro_ranking(config)

tipo = 'live-deal-digital-option' # live-deal-binary-option-placed
timeframe = 'PT'+config['timeframe']+'M' # PT5M / PT15M
old = 0

# Captura o Payout
py = float(payout(config['paridade'], 'digital', int(config['timeframe'])) / 100)

API.subscribe_live_deal(tipo, config['paridade'], timeframe, 10)

while True:
	trades = API.get_live_deal(tipo, config['paridade'], timeframe)
	
	if len(trades) > 0 and old != trades[0]['user_id'] and trades[0]['amount_enrolled'] >= float(config['valor_minimo']):
		ok = True
		
		if len(filtro_top_traders) > 0:
			if trades[0]['user_id'] not in filtro_top_traders:
				ok = False
		
		if ok:
			# Dados sinal
			print(' [',trades[0]['flag'],']',config['paridade'],'/',trades[0]['amount_enrolled'],'/',trades[0]['instrument_dir'],'/',trades[0]['name'])
			
			
			# 1 entrada
			resultado,lucro = entradas(config['paridade'], config['valor_entrada'], trades[0]['instrument_dir'], 1)
			print('   -> ',resultado,'/',lucro,'\n\n')
			
			
			# Martingale
			if resultado == 'loss' and config['martingale'] == 'S':
				valor_entrada = martingale('auto', float(config['valor_entrada']), float(py))
				for i in range(int(config['niveis']) if int(config['niveis']) > 0 else 1):
					
					print('   MARTINGALE NIVEL '+str(i+1)+'..', end='')
					resultado,lucro = entradas(config['paridade'], valor_entrada, trades[0]['instrument_dir'], 1)
					print(' ',resultado,'/',lucro,'\n')
					
					if resultado == 'win':
						print('\n')
						break
					else:
						valor_entrada = martingale('auto', float(config['valor_entrada']), float(py))
						
			elif resultado == 'loss' and config['sorosgale'] == 'S': # SorosGale
				
				if float(config['valor_entrada']) > 5:
					
					lucro_total = 0
					lucro = 0
					perca = float(config['valor_entrada']) 
					# Nivel
					for i in range(int(config['niveis']) if int(config['niveis']) > 0 else 1):
						
						# Mao
						for i2 in range(2):
						
							if lucro_total >= perca:
								break
						
							print('   SOROSGALE NIVEL '+str(i+1)+' | MAO '+str(i2+1)+' | ', end='')
							
							# Entrada
							resultado,lucro = entradas(config['paridade'], (perca / 2)+lucro, trades[0]['instrument_dir'], int(config['timeframe']))
							
							print(resultado,'/',lucro,'\n')	
							
							if resultado == 'win':			
								lucro_total += lucro
							else:
								lucro_total = 0
								perca += perca / 2								
								break						
			
			
		old = trades[0]['user_id']



API.unscribe_live_deal(tipo, config['paridade'], timeframe)
