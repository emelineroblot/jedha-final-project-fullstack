"""Tables de correspondance de l'ETL — extraites verbatim de 02_etl_pipeline.ipynb.

Isolées ici pour que `etl_pipeline.py` reste lisible et que ces mappings,
qui sont de la donnée de référence et non de la logique, soient révisables
indépendamment du code.
"""

FAO_TO_ISO3 = {
    'China, mainland'                                    : 'CHN',
    'China, Taiwan Province of'                          : 'TWN',
    'China, Hong Kong SAR'                               : 'HKG',
    'China, Macao SAR'                                   : 'MAC',
    'Bolivia (Plurinational State of)'                   : 'BOL',
    'Venezuela (Bolivarian Republic of)'                 : 'VEN',
    'United States of America'                           : 'USA',
    'United Kingdom of Great Britain and Northern Ireland': 'GBR',
    'Republic of Korea'                                  : 'KOR',
    "Democratic People's Republic of Korea"              : 'PRK',
    'Viet Nam'                                           : 'VNM',
    'Iran (Islamic Republic of)'                         : 'IRN',
    'Syrian Arab Republic'                               : 'SYR',
    "Lao People's Democratic Republic"                   : 'LAO',
    "Côte d'Ivoire"                                      : 'CIV',
    'Czech Republic'                                     : 'CZE',
    'Czechia'                                            : 'CZE',
    'Republic of Moldova'                                : 'MDA',
    'Russian Federation'                                 : 'RUS',
    'United Republic of Tanzania'                        : 'TZA',
    'United Arab Emirates'                               : 'ARE',
    'Papua New Guinea'                                   : 'PNG',
    'Congo'                                              : 'COG',
    'Democratic Republic of the Congo'                   : 'COD',
    'Eswatini'                                           : 'SWZ',
    'North Macedonia'                                    : 'MKD',
    'The former Yugoslav Republic of Macedonia'          : 'MKD',
    'Occupied Palestinian Territory'                     : 'PSE',
    'Palestine'                                          : 'PSE',
    'Timor-Leste'                                        : 'TLS',
    'Micronesia (Federated States of)'                   : 'FSM',
    'Cabo Verde'                                         : 'CPV',
    'Cape Verde'                                         : 'CPV',
    'Sao Tome and Principe'                              : 'STP',
    'Sudan (former)'                                     : 'SDN',
    # Régions agrégées FAO → pas de pays ISO (exclus du DWH)
    'Africa': None, 'Americas': None, 'Asia': None, 'Europe': None,
    'Oceania': None, 'World': None,
    'Low Income Food Deficit Countries'    : None,
    'Net Food Importing Developing Countries': None,
    'Least Developed Countries'            : None,
    'Land Locked Developing Countries'     : None,
    'Small Island Developing States'       : None,
    'Eastern Africa': None, 'Middle Africa': None, 'Northern Africa': None,
    'Southern Africa': None, 'Western Africa': None,
    'Central Asia': None, 'Eastern Asia': None, 'South-eastern Asia': None,
    'Southern Asia': None, 'Western Asia': None,
    'Eastern Europe': None, 'Northern Europe': None,
    'Southern Europe': None, 'Western Europe': None,
    'Caribbean': None, 'Central America': None, 'South America': None,
    'Northern America': None, 'Australia and New Zealand': None,
    'Melanesia': None, 'Micronesia': None, 'Polynesia': None,
    'Serbia and Montenegro': None,
}

REGION_MAP = {
    'AF':'Africa','AO':'Africa','BF':'Africa','BI':'Africa','BJ':'Africa',
    'BW':'Africa','CD':'Africa','CF':'Africa','CG':'Africa','CI':'Africa',
    'CM':'Africa','CV':'Africa','DJ':'Africa','DZ':'Africa','EG':'Africa',
    'ER':'Africa','ET':'Africa','GA':'Africa','GH':'Africa','GM':'Africa',
    'GN':'Africa','GQ':'Africa','GW':'Africa','KE':'Africa','KM':'Africa',
    'LR':'Africa','LS':'Africa','LY':'Africa','MA':'Africa','MG':'Africa',
    'ML':'Africa','MR':'Africa','MU':'Africa','MW':'Africa','MZ':'Africa',
    'NA':'Africa','NE':'Africa','NG':'Africa','RW':'Africa','SC':'Africa',
    'SD':'Africa','SL':'Africa','SN':'Africa','SO':'Africa','SS':'Africa',
    'ST':'Africa','SZ':'Africa','TD':'Africa','TG':'Africa','TN':'Africa',
    'TZ':'Africa','UG':'Africa','ZA':'Africa','ZM':'Africa','ZW':'Africa',
    'AM':'Asia','AZ':'Asia','BD':'Asia','BH':'Asia','BN':'Asia','BT':'Asia',
    'CN':'Asia','CY':'Asia','GE':'Asia','HK':'Asia','ID':'Asia','IL':'Asia',
    'IN':'Asia','IQ':'Asia','IR':'Asia','JO':'Asia','JP':'Asia','KG':'Asia',
    'KH':'Asia','KP':'Asia','KR':'Asia','KW':'Asia','KZ':'Asia','LA':'Asia',
    'LB':'Asia','LK':'Asia','MM':'Asia','MN':'Asia','MO':'Asia','MV':'Asia',
    'MY':'Asia','NP':'Asia','OM':'Asia','PH':'Asia','PK':'Asia','PS':'Asia',
    'QA':'Asia','SA':'Asia','SG':'Asia','SY':'Asia','TH':'Asia','TJ':'Asia',
    'TL':'Asia','TM':'Asia','TR':'Asia','TW':'Asia','UZ':'Asia','VN':'Asia',
    'YE':'Asia',
    'AL':'Europe','AT':'Europe','BA':'Europe','BE':'Europe','BG':'Europe',
    'BY':'Europe','CH':'Europe','CZ':'Europe','DE':'Europe','DK':'Europe',
    'EE':'Europe','ES':'Europe','FI':'Europe','FR':'Europe','GB':'Europe',
    'GR':'Europe','HR':'Europe','HU':'Europe','IE':'Europe','IS':'Europe',
    'IT':'Europe','LI':'Europe','LT':'Europe','LU':'Europe','LV':'Europe',
    'MD':'Europe','ME':'Europe','MK':'Europe','MT':'Europe','NL':'Europe',
    'NO':'Europe','PL':'Europe','PT':'Europe','RO':'Europe','RS':'Europe',
    'RU':'Europe','SE':'Europe','SI':'Europe','SK':'Europe','SM':'Europe',
    'UA':'Europe',
    'AG':'Americas','AR':'Americas','BB':'Americas','BO':'Americas',
    'BR':'Americas','BS':'Americas','BZ':'Americas','CA':'Americas',
    'CL':'Americas','CO':'Americas','CR':'Americas','CU':'Americas',
    'DO':'Americas','EC':'Americas','GT':'Americas','GY':'Americas',
    'HN':'Americas','HT':'Americas','JM':'Americas','KN':'Americas',
    'LC':'Americas','MX':'Americas','NI':'Americas','PA':'Americas',
    'PE':'Americas','PY':'Americas','SR':'Americas','SV':'Americas',
    'TT':'Americas','US':'Americas','UY':'Americas','VC':'Americas',
    'VE':'Americas',
    'AU':'Oceania','FJ':'Oceania','KI':'Oceania','NR':'Oceania',
    'NZ':'Oceania','PG':'Oceania','PW':'Oceania','SB':'Oceania',
    'TO':'Oceania','TV':'Oceania','VU':'Oceania','WS':'Oceania',
}

def categorize(name):
    n = name.lower()
    if any(w in n for w in ['bovine','beef','mutton','goat','pig','pork','poultry','chicken','lamb','meat','offal']):
        sub = 'Bovine' if 'bovine' in n or 'beef' in n else               'Sheep/Goat' if 'mutton' in n or 'goat' in n else               'Pork' if 'pig' in n or 'pork' in n else               'Poultry' if 'poultry' in n or 'chicken' in n else 'Other'
        return 'Meat', sub
    if any(w in n for w in ['milk','cheese','butter','dairy','ghee','cream','whey','lactose']):
        return 'Dairy', 'Other'
    if any(w in n for w in ['egg']):
        return 'Eggs', 'Eggs'
    if any(w in n for w in ['fish','seafood','shrimp','salmon','tuna','crab','aquatic','mollusc']):
        return 'Fish & Seafood', 'Other'
    if any(w in n for w in ['wheat','rye','barley','oat','millet','sorghum','cereal','maize','corn','rice','grain','buckwheat']):
        return 'Cereals', 'Other'
    if any(w in n for w in ['soy','pea','bean','lentil','pulse','legume','groundnut','chickpea','cowpea','pigeon']):
        return 'Legumes', 'Other'
    if any(w in n for w in ['nut','cashew','almond','walnut','hazelnut','pistachio']):
        return 'Nuts', 'Other'
    if any(w in n for w in ['palm','sunflower','rapeseed','olive','soybean oil','vegetable oil','oilcrop','cotton','linseed','sesame']):
        return 'Oils & Fats', 'Other'
    if any(w in n for w in ['sugar cane','sugar beet','sugar','sweetener','fructose']):
        return 'Sugar', 'Other'
    if any(w in n for w in ['potato','cassava','yam','taro','tuber','root','sweet potato']):
        return 'Roots & Tubers', 'Other'
    if any(w in n for w in ['tomato','onion','carrot','cabbage','pepper','lettuce','spinach','vegetable','cucumber','garlic','leek']):
        return 'Vegetables', 'Other'
    if any(w in n for w in ['apple','orange','banana','grape','mango','pineapple','citrus','fruit','berr','melon','pear','avocado']):
        return 'Fruits', 'Other'
    if any(w in n for w in ['coffee','tea','cocoa','cacao','mate']):
        return 'Beverages & Stimulants', 'Other'
    if any(w in n for w in ['wine','beer','alcohol','spirit','fermented']):
        return 'Alcohol', 'Other'
    if any(w in n for w in ['spice','pepper','ginger','cinnamon','vanilla','herb']):
        return 'Spices', 'Other'
    return 'Other', None
