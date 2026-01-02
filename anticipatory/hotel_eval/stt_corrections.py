"""
Speech-to-text error corrections for common transcription mistakes.
Contains patterns for fixing phonetically similar words that STT often mishears.
"""

import re
from typing import List, Tuple, Union

# STT correction patterns: (pattern, replacement) or (pattern, replacement, flags)
STT_CORRECTION_PATTERNS: List[Union[Tuple[str, str], Tuple[str, str, int]]] = [
    # Booking-related
    (r'\bbouquet\s*numbers?\b', 'booking number'),
    (r'\bbucket\s*numbers?\b', 'booking number'),
    (r'\bbooking\s*numbers\b', 'booking number'),  # plural to singular
    (r'\bbook\s+king\b', 'booking'),
    (r'\bbuff[ei]ng?\s*number\b', 'booking number'),

    # Hotel/Resort names - Tamara variations
    (r'\btamara\s*c(?:ourt|ork|ore|orps?|ord|hord)\b', 'Tamara Coorg'),
    (r'\btamar[io]?\s*(?:cord|gord|korg|corgan)\b', 'Tamara Coorg'),
    (r'\bthe\s*(?:temar|tamer|tamar|tim\s*[ar]+|temmer|timmer)\s*(?:resorts?|resource?s?|reserve?s?|rover\s*2?|reserve)?\b', 'The Tamara Resorts'),
    (r'\b(?:temar|tamer|tamar|temmer|timmer)\s*(?:resorts?|resource?s?|reserve?s?|revour)\b', 'Tamara Resorts'),
    (r'\btamara\s*(?:kodiak?|koda|kodi|kode)\b', 'Tamara Kodaikanal'),
    (r'\btamara\s*kodaikanal\b', 'Tamara Kodaikanal'),
    (r'\btemara\s*kode\b', 'Tamara Kodaikanal'),
    (r'\btemara(?:de)?\b', 'Tamara'),
    (r'\bthe\s+tomorrow\b', 'The Tamara'),
    (r'\btmr\s*(?:results?|resorts?)\b', 'Tamara Resorts'),
    (r'\btim\s*r\s*resorts?\b', 'Tamara Resorts'),
    (r'\b10\s*(?:more|hour|our)\s*resorts?\b', 'Tamara Resorts'),
    (r'\btamer\s*verse\b', 'Tamara Resorts'),
    (r'\btamar\s*research\b', 'Tamara Resorts'),

    # Common Indian names (STT often mishears)
    (r'\bsyndrome\b', 'Sundaram'),
    (r'\bsunder(?:ram|ham)\b', 'Sundaram'),
    (r'\bchindrom\b', 'Sundaram'),
    (r'\bminachi\s*(?:suram|sunderram)?\b', 'Meenakshi Sundaram'),
    (r'\bmean\s*(?:fc|actually)\s*(?:syndrome|sunderham|sundaram)?\b', 'Meenakshi Sundaram'),
    (r'\bmina\b', 'Meena'),
    (r'\b(?:emmet|emmett|emman|emmit)\b', 'Amit'),
    (r'\blimit\b(?=.*(?:phone|number|mobile))', 'Amit'),
    (r'\bamy\b(?=.*(?:tamara|coorg|booking))', 'Amit'),
    (r'\b(?:benjat|benja)\b', 'Venkat'),
    (r'\bband\s*cap\b', 'Venkat'),
    (r'\bthen\s*at\b', 'Venkat'),
    (r'\bvinked\b', 'Venkat'),
    (r'\bvincan\b', 'Venkat'),
    (r'\bben\s*cat\b', 'Venkat'),
    (r'\bpama\b', 'Padma'),
    (r'\btad\s*mah\b', 'Padma'),
    (r'\bhannah?\b(?=.*(?:tamara|booking|cottage))', 'Padma'),
    (r'\bketha\b', 'Kavitha'),
    (r'\bdivy\b', 'Divya'),
    (r'\bdivia\b', 'Divya'),
    (r'\bdeviation\b(?=.*(?:name|shankar))', 'Divya'),
    (r'\bdivision\b(?=.*(?:name|shankar|car))', 'Divya'),
    (r'\bdr\.?\s*(?:rider|romation)\b', 'Dr. Ramakrishnan'),
    (r'\bnina\b(?=.*(?:tamara|coorg|booking))', 'Meena'),
    (r'\bsandy\b', 'Sandeep'),
    (r'\bsend\s*deep\b', 'Sandeep'),
    (r'\b(?:milan|neiland?|nel[ae]m?|nelm|nela|neil?a?m?p?)\b(?=.*(?:tamara|kodai|booking|cottage|phone))', 'Neelam'),
    (r'\bnew\s*lamp\b', 'Neelam'),
    (r'\bme\s*limp\b', 'Neelam'),
    (r'\baaron\b', 'Arun'),
    (r'\barum\b', 'Arun'),
    (r'\banne?\b(?=.*(?:tamara|guests?|traveling))', 'Arun'),
    (r'\banna\b(?=.*(?:phone|number|correct))', 'Anil'),
    (r'\btin\s*b\b', 'Tanvi'),
    (r'\btan\s*bi\b', 'Tanvi'),
    (r'\bten\s*b(?:eat|i)?\b', 'Tanvi'),
    (r'\bcandy\b(?=.*(?:cottage|booking|stay))', 'Tanvi'),
    (r'\bcan\s*be\b(?=.*(?:email|cottage|booking))', 'Tanvi'),
    (r'\bvickhamp?\b', 'Vikram'),
    (r'\bvicram\b', 'Vikram'),
    (r'\bweekend\b(?=.*(?:phone|number|correct))', 'Vikram'),
    (r'\bthresh\b', 'Suresh'),
    (r'\bseresh\b', 'Suresh'),
    (r'\b(?:harsh|harish)\b', 'Harish'),
    (r'\bfeel\b(?=.*(?:booking|recap|tamara|cottage))', 'Theo'),
    (r'\badded\b(?=.*(?:phone|email|booking))', 'Aditya'),
    (r'\bshri\b(?=.*(?:tamara|booking|cottage))', 'Shreya'),
    (r'\bsith\b(?=.*(?:name|das))', 'Siddharth'),
    (r'\bsiddharth\s+dust\b', 'Siddharth Das'),
    (r'\bsiddharth\s+das\b', 'Siddharth Das'),
    (r'\bten\s*b\b(?=.*(?:email|m@))', 'Tanvi'),
    (r'\benvy\b(?=.*(?:email|apologies|tamara))', 'Tanvi'),
    (r'\btamby\b', 'Tanvi'),
    (r'\bdebe\b', 'Deepa'),
    (r'\bthe\s+guy\b(?=.*(?:apologies|unable|email))', 'Deepa'),
    (r'\bkarto\b', 'Karthik'),
    (r'\bsweaty\b(?=.*(?:apologies|reservation))', 'Swati'),
    (r'\bswatty\b', 'Swati'),

    # Common STT word confusions
    (r'\bwrite\s+that\b', 'right back'),
    (r'\bjust\s+in\s+(?:taste|a\s+case)\b', 'just in case'),
    (r'\binfirm\b', 'confirm'),
    (r'\bd(?:ige|ive|odge)\s*(?:you)?\s*better\b', 'guide you better'),
    (r'\bbuy\s+you\s+better\b', 'guide you better'),
    (r'\bthank\s+you\s+better\b', 'guide you better'),
    (r'\bvote\s+you\s+better\b', 'guide you better'),
    (r'\btell\s+you\s+better\b', 'guide you better'),
    (r'\b(?:yeah|ya|yah),?\s+i\s+know\s+your\s+name\b', 'May I know your name'),
    (r'\bi\s+know\s+your\s+name\s*,?\s*please\b', 'May I know your name, please'),
    (r'\bi\s+know\s+your\s+name\s+is\b', 'May I know your name'),
    (r'\bthis\s+is\s+\.?\s*i\'d\s+be\s+delighted\b', 'This is Sarah. I\'d be delighted'),
    (r'\btheble\b', 'unable'),
    (r'\bincaparing\b', 'encountering'),
    (r'\bencom+er+ing\b', 'encountering'),
    (r'\bintervenience\b', 'inconvenience'),
    (r'\bstill\s+in\s+cannot\s+issue\b', 'still encountering an issue'),
    (r'\bstill\s+cannot\s+issue\b', 'still encountering an issue'),
    (r'\beasiness\b', 'eagerness'),
    (r'\beveness\b', 'eagerness'),
    (r'\breagan+ess\b', 'eagerness'),
    (r'\bidealized\b', 'ideal'),
    (r'\bperceive\b(?=.*booking)', 'proceed with'),
    (r'\bstate\b(?=.*(?:nights?|luxury|cottage|booking|restful))', 'stay'),
    (r'\b(?:it|git)\s*away\b', 'getaway'),
    (r'\bgetit\s*away\b', 'getaway'),
    (r'\bway\b(?=.*(?:restful|experiential))', 'getaway'),
    (r'\bItaly\b(?=.*(?:restful|hoping))', 'getaway'),
    (r'\bso\s*line\b', 'so we\'re aligned'),
    (r'\bcounting\b(?=.*(?:technical|phone))', 'encountering'),
    (r'\bfix\s+up\b', 'hiccup'),
    (r'\bsick\s+up\b', 'hiccup'),
    (r'\b(?:how\s+)?many\s+(?:I\s+)?assist\s+you\b', 'may I assist you'),

    # Room/accommodation terms
    (r'\bluxury\s*(?:sweet|sweat)\b', 'luxury suite'),
    (r'\bluc?r?atory\s*cottage\b', 'luxury cottage'),
    (r'\bletter\s*cottage\b', 'luxury cottage'),
    (r'\blucky\s*cottages?\b', 'luxury cottages'),
    (r'\btrainful\b', 'tranquil'),
    (r'\brestortive\b', 'restorative'),
    (r'\bresortive\b', 'restorative'),
    (r'\barrestful\b', 'a restful'),
    (r'\bresponsive\b(?=.*(?:nature|getaway|stay))', 'restful'),
    (r'\bserena\s+atmosphere\b', 'serene atmosphere'),
    (r'\bserena\b(?=.*(?:atmosphere|peaceful|tranquil))', 'serene'),
    (r'\bwelcher\s+friendly\b', 'wheelchair friendly'),
    (r'\bwhirl\s+friendly\b', 'wheelchair friendly'),
    (r'\broland\s+bath(?:ering|room)?\b', 'roll-in bathroom'),

    # Activity/experience terms
    (r'\ball\s+males\b', 'all meals'),
    (r'\bcurious\s+activities\b', 'curated activities'),
    (r'\bperiod\s+activities\b', 'curated activities'),
    (r'\bcharity\s+activities\b', 'curated activities'),
    (r'\bcharitated\s+activities\b', 'curated activities'),
    (r'\bAmerican\s+plan\b', 'meal plan'),
    (r'\b180\s*a\s*go\b', '180 acres'),
    (r'\b\$180\s*acres\b', '180 acres'),
    (r'\b180\s*dollars\s*acres\b', '180 acres'),

    # Misc STT errors
    (r'\bmiss\b(?=.*(?:tree|house|floating|cottage|plantation))', 'mist'),
    (r'\bmess\b(?=.*(?:tree|house|floating|plantation))', 'mist'),
    (r'\bnest\b(?=.*(?:tree|house|floating|plantation|coffee))', 'mist'),
    (r'\bfloating\s+in\s+the\s+(?:nest|miss)\b', 'floating in the mist'),
    (r'\bsenate\s+(?:mountain|view)', 'serene'),
    (r'\bneed\s+your\s+focused\b', 'nature-focused'),
    (r'\bnature\s+your\s+focused\b', 'nature-focused'),
    (r'\bfall\s+meals\b', 'all meals'),
    (r'\benhance\s+amenities\b', 'enhanced amenities'),
    (r'\bhumanities\b', 'amenities'),
    (r'\bhumidities\b', 'amenities'),
    (r'\bin\s*handsomeity\b', 'enhanced amenity'),
    (r'\bhands\s+humidities\b', 'enhanced amenities'),
    (r'\benhanced\s+humanities\b', 'enhanced amenities'),
    (r'\bvalue\b(?=.*(?:creating|serene))', 'view'),
    (r'\bonline\b(?=.*(?:relax|unwind|reflection))', 'unwind'),
    (r'\btender\s+visit\b', 'wonderful visit'),
    (r'\bmagical\s+tender\b', 'magical'),
    (r'\bhold\s+up\b', 'holdup'),
    (r'\bdesk\b(?=.*(?:traveling|guests?))', 'guests'),
    (r'\bdips\b(?=.*traveling)', 'guests'),
    (r'\bdiscs?\b(?=.*traveling)', 'guests'),
    (r'\bguts\b(?=.*traveling)', 'guests'),
    (r'\bdeath\b(?=.*(?:traveling|cottage|looking|train))', 'guests'),
    (r'\bdeath\s+looking\s+for\b', 'guests looking for'),
    (r'\bcomes?\s+dry\s+and\s+are\b', 'comes to INR'),
    (r'\brnr\b', 'INR'),
    (r'\bkodal\b', 'total'),

    # Currency/pricing
    (r'\binr\s+(\d)', r'INR \1'),
    (r'\bi\s*n\s*r\b', 'INR'),

    # Common word corrections
    (r'\bwonderfull?\b', 'wonderful'),
    (r'\bbeautifull?\b', 'beautiful'),
    (r'\bdelightfull?\b', 'delightful'),
    (r'\bcottedge\b', 'cottage'),
    (r'\bcotage\b', 'cottage'),
    (r'\bresorte?\b(?=\s)', 'resort'),
    (r'\bsincerly\b', 'sincerely'),
    (r'\blovel+y\b', 'lovely'),
    (r'\bserious\s+apologies\b', 'sincere apologies'),
    (r'\bmy\s+sincer\s+apologies\b', 'my sincere apologies'),

    # Confirmation-related
    (r'\bconfirmationed?\b', 'confirmed'),
    (r'\breservated\b', 'reserved'),
]


def clean_stt_errors(text: str) -> str:
    """
    Clean common STT transcription errors to improve transcript readability.
    These are phonetically similar words that STT often mishears.

    Args:
        text: Raw transcribed text

    Returns:
        Cleaned text with common STT errors corrected
    """
    result = text
    for correction in STT_CORRECTION_PATTERNS:
        if len(correction) == 2:
            pattern, replacement = correction
            flags = re.IGNORECASE
        else:
            pattern, replacement, flags = correction

        result = re.sub(pattern, replacement, result, flags=flags)

    return result
