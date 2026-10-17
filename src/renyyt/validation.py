import re
from datetime import datetime
from .errors import ApiError

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_scalar_interval(value):
    return value is None or (isinstance(value, (str, int, float)) and not isinstance(value, bool))


def _warning(index, field, code, message):
    return {"serviceIndex": index, "field": field, "code": code, "message": message}


def validate_services_payload(data):
    """Validate the envelope strictly, individual services permissively.

    Unknown fields are accepted. Service-level shape changes become diagnostics so a
    single partially changed service does not make all otherwise usable data fail.
    """
    if not isinstance(data, list):
        raise ApiError("UPSTREAM_SCHEMA_ERROR", "Renyyn palauttaman datan rakenne ei vastannut odotettua palvelulistaa.", 502)

    warnings = []
    for index, service in enumerate(data):
        if not isinstance(service, dict):
            warnings.append(_warning(index, "", "SERVICE_NOT_OBJECT", "Palvelulistan alkio ei ollut JSON-objekti."))
            continue

        next_date = service.get("ASTNextDate")
        if next_date is not None:
            valid = isinstance(next_date, str) and bool(DATE_RE.match(next_date))
            if valid:
                try:
                    datetime.strptime(next_date, "%Y-%m-%d")
                except ValueError:
                    valid = False
            if not valid:
                warnings.append(_warning(index, "ASTNextDate", "INVALID_DATE", "The collection date format was unexpected."))

        for field in ("ASTVali", "ASTVali2", "ASTVoim1", "ASTVoim2", "ASTVoim21", "ASTVoim22"):
            if not _is_scalar_interval(service.get(field)):
                warnings.append(_warning(index, field, "INVALID_SCALAR", "The %s field format was unexpected." % field))

        tariff = service.get("tariff")
        if tariff is not None and not isinstance(tariff, dict):
            warnings.append(_warning(index, "tariff", "INVALID_OBJECT", "The tariff field structure was unexpected."))
        elif isinstance(tariff, dict):
            pg = tariff.get("productgroup")
            if pg is not None and not isinstance(pg, str):
                warnings.append(_warning(index, "tariff.productgroup", "INVALID_STRING", "The product group field format was unexpected."))

        kimppa = service.get("kimppa")
        if kimppa is not None and not isinstance(kimppa, dict):
            warnings.append(_warning(index, "kimppa", "INVALID_OBJECT", "The kimppa field structure was unexpected."))

        kirpros = service.get("KIRPros")
        if kirpros is not None and not _is_scalar_interval(kirpros):
            warnings.append(_warning(index, "KIRPros", "INVALID_SCALAR", "The shared-bin percentage format was unexpected."))

    return warnings


# Known upstream fields for diagnostics. Unknown fields are not validation errors;
# they are logged only as structural debug information without values.
KNOWN_SERVICE_FIELDS = {
    "lease", "status", "akpId", "tariff", "kimppa", "washingRing", "ASTAsnro",
    "ASTTyyppi", "ASTPos", "id", "ASTHaku", "ASTMaara", "ASTHinta", "ASTKasit",
    "ASTVoim1", "ASTVoim2", "ASTVali", "ASTKrtvk", "AST1vko", "ASTVoim21",
    "ASTVoim22", "ASTVali2", "ASTKrtvk2", "AST1vko2", "ASTPaivat", "ASTAlkPvm",
    "ASTLopPvm", "ASTUrak", "ASTMatka", "ASTPerMatka", "ASTMatkaPAs",
    "ASTPerMatkaPAs", "ASTTunn", "ASTX", "ASTY", "ASTZ", "ASTHintaId",
    "ASTLisaPvm", "ASTOPaino", "ASTOmistaja", "ASTEdHinta", "ASTEdKasit",
    "ASTEdPvm", "ASTKuljAlennus", "ASTKuljAlk", "ASTKuljAst", "ASTKasAlennus",
    "ASTKasAlk", "ASTKasAst", "ASTAvain", "ASTKeskAlk", "ASTKeskAst", "ASTKuljKom",
    "ASTKuljKomAlk", "ASTKuljKomAst", "ASTLastModBy", "ASTLastModDate",
    "ASTLastModTime", "ASTCreatedDte", "ASTKomm", "ASTSeurTyhj", "ASTNextDate",
    "ASTPaikanna", "ASTLHinta", "ASTAsTilNro", "ASTAsKustPaik", "ASTKALTunnus",
    "KIRPros", "akp", "kimppaisanta", "ASTNimi", "ASTYks",
}
KNOWN_TARIFF_FIELDS = {
    "id", "productgroup", "recyclingrate", "weightBased", "defaultWeight", "price",
    "wprice", "logo", "defaultOrderType", "amendmentAllowed", "customerOrderable",
    "visibleForCustomer", "subcategory", "name", "unit", "EWCId", "RDId",
    "description", "weightunit", "size",
}
KNOWN_KIMPPA_FIELDS = {
    "status", "osakkaat", "isanta", "KIMKimppa", "KIMTyyppi", "KIMNimi1",
    "KIMNimi4", "KIMLastModBy", "KIMLastModDate", "KIMLastModTime",
    "KIMCreatedDte", "KIMCreatedBy", "KIMCreatedTime", "KIMVastaava", "KIMComm",
    "KIMMaara",
}

def _json_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__

def collect_unknown_fields(data):
    """Return only field paths and JSON-ish types; never values."""
    diagnostics = []
    if not isinstance(data, list):
        return diagnostics
    seen = set()
    for service in data:
        if not isinstance(service, dict):
            continue
        for key, value in service.items():
            if key not in KNOWN_SERVICE_FIELDS:
                item = (str(key), _json_type(value))
                if item not in seen:
                    seen.add(item); diagnostics.append({"field": item[0], "type": item[1]})
        tariff = service.get("tariff")
        if isinstance(tariff, dict):
            for key, value in tariff.items():
                if key not in KNOWN_TARIFF_FIELDS:
                    item = ("tariff.%s" % key, _json_type(value))
                    if item not in seen:
                        seen.add(item); diagnostics.append({"field": item[0], "type": item[1]})
        kimppa = service.get("kimppa")
        if isinstance(kimppa, dict):
            for key, value in kimppa.items():
                if key not in KNOWN_KIMPPA_FIELDS:
                    item = ("kimppa.%s" % key, _json_type(value))
                    if item not in seen:
                        seen.add(item); diagnostics.append({"field": item[0], "type": item[1]})
    return diagnostics
