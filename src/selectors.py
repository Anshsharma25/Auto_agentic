# src/selectors.py

# login selectors
USERNAME_INPUT = 'input#logFld_885_73_2_1'
PASSWORD_INPUT = 'input#logFld_885_73_2_2'
LOGIN_BUTTON_IMG = 'img.logBtnLogin'
CONTINUE_BUTTON = 'input[name="CONFIRMAR"][value="Continuar"]'

# Consulta de CFE recibidos page selectors
SELECT_TIPO_CFE = 'select#vFILTIPOCFE'            # dropdown for tipo CFE
DATE_FROM = 'input#CTLFECHADESDE'                 # 'Desde' date field
DATE_TO = 'input#CTLFECHAHASTA'                   # 'Hasta' date field
BUTTON_CONSULTAR = 'input[name="BOTONCONSULTAR"]' # Consultar button

# Export selectors (the highlighted input type="image" in your screenshot)
EXPORT_XLS_BY_NAME = 'input[name="EXPORTXLS"]'
EXPORT_XLS_BY_ID = 'input#EXPORTXLS'
EXPORT_XLS_IMG = 'input[type="image"][name="EXPORTXLS"]'
