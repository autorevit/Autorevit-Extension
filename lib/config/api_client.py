# -*- coding: utf-8 -*-
"""
lib/config/api_client.py - VERSION CORRIGÉE JWT + REFRESH TOKEN

✅ CORRECTION v2: Refresh token automatique sur expiration (401)
✅ CORRECTION v1: Utilise JWT token (Authorization: Bearer)

Compatible IronPython 2.7 (Revit/pyRevit)
"""

import os
import json
import time

try:
    from io import open as io_open
except ImportError:
    io_open = open

try:
    import urllib2
    HAS_URLLIB2 = True
except ImportError:
    import urlrequest as urllib2
    HAS_URLLIB2 = False

# ============================================================================
# EXCEPTIONS
# ============================================================================

class APIError(Exception): pass
class APIConnectionError(APIError): pass
class APIAuthenticationError(APIError): pass
class APIPermissionError(APIError): pass
class APINotFoundError(APIError): pass
class APITimeoutError(APIError): pass
class OfflineModeRestrictedError(APIError): pass

class APIResponseError(APIError):
    def __init__(self, status_code, message):
        self.status_code = status_code
        super(APIResponseError, self).__init__(message)

DEFAULT_TIMEOUT    = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 3


# ============================================================================
# CLIENT API PRINCIPAL
# ============================================================================

class APIClient(object):

    def __init__(self, settings):
        self.base_url     = settings.api_url.rstrip('/')
        self.timeout      = getattr(settings, 'api_timeout',   DEFAULT_TIMEOUT)
        self.max_retries  = getattr(settings, 'max_retries',   DEFAULT_MAX_RETRIES)
        self.retry_delay  = getattr(settings, 'retry_delay',   DEFAULT_RETRY_DELAY)
        self.offline_mode = getattr(settings, 'offline_mode',  False)

        self.session_token = None
        self.refresh_token = None      # ✅ NOUVEAU
        self._refreshing   = False     # ✅ NOUVEAU - anti boucle infinie

        self.headers = {
            'Content-Type': 'application/json',
            'Accept':       'application/json',
        }

        self.cache_dir = getattr(
            settings, 'cache_dir',
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'cache')
        )
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        self.token_file = os.path.join(self.cache_dir, 'session_token.json')
        self._load_session_token()

    # -----------------------------------------------------------------------
    # GESTION JWT TOKEN
    # -----------------------------------------------------------------------

    def _load_session_token(self):
        if os.path.exists(self.token_file):
            try:
                with io_open(self.token_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.session_token = data.get('session_token')
                self.refresh_token = data.get('refresh_token')   # ✅ NOUVEAU
                if self.session_token:
                    self.headers['Authorization'] = 'Bearer ' + str(self.session_token)
                    print("Info: JWT token charge depuis cache")
                    return True
            except Exception as e:
                print("Warning: JWT token cache invalide : " + str(e))
        self.session_token = None
        self.refresh_token = None
        return False

    def _save_session_token(self):
        if self.session_token:
            try:
                with io_open(self.token_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'session_token': self.session_token,
                        'refresh_token': self.refresh_token,     # ✅ NOUVEAU
                    }, f, indent=2, ensure_ascii=False)
                print("Debug: JWT token sauvegarde")
            except Exception as e:
                print("Error: Impossible de sauvegarder le JWT token : " + str(e))

    def is_authenticated(self):
        return self.session_token is not None

    def refresh_access_token(self):
        """
        ✅ NOUVEAU - Renouvelle l'access token via le refresh token.
        Appele automatiquement sur erreur 401.
        Retourne True si succes, False sinon.
        """
        if not self.refresh_token:
            print("Warning: Pas de refresh token - reconnexion requise")
            return False
        if self._refreshing:
            print("Warning: Refresh deja en cours - abandon")
            return False

        self._refreshing = True
        try:
            print("Info: Tentative de renouvellement du token JWT...")
            response = self._make_request(
                "POST", "auth/token/refresh/",
                {"refresh": self.refresh_token},
                auth_required=False
            )
            new_access = response.get('access') if response else None
            if not new_access:
                print("Warning: Reponse refresh invalide")
                return False

            self.session_token = new_access
            self.headers['Authorization'] = 'Bearer ' + str(new_access)
            new_refresh = response.get('refresh')
            if new_refresh:
                self.refresh_token = new_refresh
            self._save_session_token()
            print("Info: Access token renouvele avec succes")
            return True

        except Exception as e:
            print("Warning: Echec renouvellement token : " + str(e))
            return False
        finally:
            self._refreshing = False

    def clear_tokens(self):
        """
        ✅ NOUVEAU - Vide les tokens memoire + disque.
        Appele quand le refresh token est aussi expire.
        """
        self.session_token = None
        self.refresh_token = None
        self.headers.pop('Authorization', None)
        if os.path.exists(self.token_file):
            try:
                os.remove(self.token_file)
                print("Info: Tokens supprimes - reconnexion requise")
            except Exception as e:
                print("Warning: Impossible de supprimer token : " + str(e))

    # -----------------------------------------------------------------------
    # REQUETES HTTP
    # -----------------------------------------------------------------------

    def _make_request(self, method, endpoint, data=None, auth_required=True, params=None):
        if self.offline_mode:
            raise OfflineModeRestrictedError("Mode offline - " + method + " " + endpoint + " impossible")

        url = self.base_url + "/" + endpoint.lstrip('/')
        if params:
            parts = [str(k) + '=' + str(v) for k, v in params.items() if v is not None]
            if parts:
                url = url + '?' + '&'.join(parts)

        retries_left = self.max_retries

        while retries_left > 0:
            try:
                req_data = json.dumps(data).encode('utf-8') if data is not None else None

                if auth_required and not self.session_token:
                    raise APIAuthenticationError("Authentification requise mais aucun JWT token valide")

                print("Debug: -> " + method.upper() + " " + url)

                req = urllib2.Request(url, req_data)
                for header, value in self.headers.items():
                    req.add_header(header, value)

                http_method = method.upper()
                if http_method not in ("GET", "POST"):
                    req.get_method = lambda: http_method

                resp   = urllib2.urlopen(req, timeout=self.timeout)
                status = resp.getcode()
                body   = resp.read().decode('utf-8')

                if status >= 400:
                    try:
                        err = json.loads(body)
                        msg = err.get('detail') or err.get('error') or body
                    except ValueError:
                        msg = body
                    if status == 401: raise APIAuthenticationError(msg)
                    elif status == 403: raise APIPermissionError(msg)
                    elif status == 404: raise APINotFoundError(msg)
                    elif status in (408, 504): raise APITimeoutError(msg)
                    else: raise APIResponseError(status, msg)

                try:
                    return json.loads(body) if body else None
                except ValueError:
                    raise APIResponseError(status, "Reponse non-JSON")

            except APIAuthenticationError:
                # ✅ NOUVEAU - Tentative de refresh automatique avant abandon
                if auth_required and not self._refreshing and self.refresh_token:
                    print("Info: 401 recu - tentative de refresh...")
                    if self.refresh_access_token():
                        retries_left -= 1
                        continue   # retry avec le nouveau token
                    else:
                        self.clear_tokens()
                        raise APIAuthenticationError(
                            "JWT token expire et refresh impossible - reconnexion requise"
                        )
                raise

            except (APIPermissionError, APINotFoundError, APIResponseError,
                    APITimeoutError, OfflineModeRestrictedError):
                raise

            except Exception as e:
                err_str = str(e).lower()

                if 'timeout' in err_str or 'timed out' in err_str:
                    retries_left -= 1
                    if retries_left == 0:
                        raise APITimeoutError("Timeout sur " + url + ": " + str(e))
                    time.sleep(self.retry_delay)
                    continue

                if hasattr(e, 'code'):
                    code = e.code
                    if code == 401:
                        # ✅ NOUVEAU - meme logique pour les erreurs urllib
                        if auth_required and not self._refreshing and self.refresh_token:
                            if self.refresh_access_token():
                                retries_left -= 1
                                continue
                            else:
                                self.clear_tokens()
                                raise APIAuthenticationError(
                                    "JWT token expire et refresh impossible - reconnexion requise"
                                )
                        raise APIAuthenticationError("JWT token expire ou invalide")
                    elif code == 403: raise APIPermissionError("Acces refuse")
                    elif code == 404: raise APINotFoundError("Ressource non trouvee : " + url)
                    else:
                        retries_left -= 1
                        if retries_left == 0:
                            raise APIResponseError(code, str(e))
                        time.sleep(self.retry_delay)
                        continue

                if hasattr(e, 'reason') or 'urlopen error' in err_str or 'connection' in err_str:
                    raise APIConnectionError("Erreur connexion " + url + ": " + str(e))

                raise APIConnectionError("Erreur inconnue " + url + ": " + str(e))

        raise APIConnectionError("Echec apres " + str(self.max_retries) + " tentatives sur " + url)

    # -----------------------------------------------------------------------
    # AUTHENTIFICATION
    # -----------------------------------------------------------------------

    def test_connection(self):
        try:
            self._make_request("GET", "health/", auth_required=False)
            print("Info: Connexion API OK")
            return True
        except Exception as e:
            print("Warning: Echec connexion : " + str(e))
            return False

    def login(self, username, password, revit_version='', machine_name=''):
        try:
            response = self._make_request("POST", "auth/login/", {
                "username": username, "password": password,
                "revit_version": revit_version, "machine_name": machine_name
            }, auth_required=False)

            jwt_token = response.get('access')
            if not jwt_token:
                raise APIAuthenticationError("Aucun access token retourne")

            self.session_token = jwt_token
            self.refresh_token = response.get('refresh')   # ✅ NOUVEAU
            self.headers['Authorization'] = 'Bearer ' + str(jwt_token)
            self._save_session_token()
            print("Info: Login reussi pour " + str(username))
            return response

        except APIAuthenticationError:
            raise
        except Exception as e:
            raise APIAuthenticationError("Echec login : " + str(e))

    def logout(self):
        if self.session_token:
            try:
                self._make_request("POST", "auth/logout/", {})
            except Exception:
                pass
        self.clear_tokens()   # ✅ NOUVEAU - remplace l'ancienne logique

    def get_current_user(self):
        return self._make_request("GET", "auth/profile/")

    def get_user_preferences(self):
        return self._make_request("GET", "auth/preferences/")

    def update_user_preferences(self, preferences):
        return self._make_request("PATCH", "auth/preferences/", preferences)

    def get_ui_config(self):
        return self._make_request("GET", "ui/config/", auth_required=False)

    def get_ui_config_authenticated(self):
        return self._make_request("GET", "ui/full-config/")

    # -----------------------------------------------------------------------
    # PROJETS
    # -----------------------------------------------------------------------

    def get_projects(self, active_only=True, status=None):
        params = {}
        if active_only and status is None: params['status'] = 'active'
        elif status: params['status'] = status
        return self._make_request("GET", "projects/", params=params)

    def get_project_detail(self, project_id):
        return self._make_request("GET", "projects/" + str(project_id) + "/")

    def create_project(self, project_data):
        return self._make_request("POST", "projects/", project_data)

    def update_project(self, project_id, project_data):
        return self._make_request("PATCH", "projects/" + str(project_id) + "/", project_data)

    def get_project_phases(self, project_id):
        return self._make_request("GET", "projects/" + str(project_id) + "/phases/")

    def update_project_phase(self, project_id, phase_code, phase_data):
        return self._make_request("PATCH", "projects/" + str(project_id) + "/phases/" + phase_code + "/", phase_data)

    def get_project_team(self, project_id):
        return self._make_request("GET", "projects/" + str(project_id) + "/team/")

    # -----------------------------------------------------------------------
    # NORMES
    # -----------------------------------------------------------------------

    def get_norms(self, country=None, active=True):
        params = {'is_active': active}
        if country: params['country'] = country
        return self._make_request("GET", "norms/", params=params)

    def get_norm_detail(self, norm_id):
        return self._make_request("GET", "norms/" + str(norm_id) + "/")

    def get_norm_sections(self, norm_id):
        return self._make_request("GET", "norms/" + str(norm_id) + "/sections/")

    def get_dtu_list(self, active=True):
        return self._make_request("GET", "dtu/", params={'is_active': active})

    def get_building_codes(self):
        return self._make_request("GET", "building-codes/")

    def get_normative_coefficients(self, norm_code=None, national_annex='FR'):
        params = {'national_annex': national_annex}
        if norm_code: params['norm__code'] = norm_code
        return self._make_request("GET", "parameters/coefficients/", params=params)

    # -----------------------------------------------------------------------
    # PARAMETRES
    # -----------------------------------------------------------------------

    def get_parameters(self, category=None, is_system=None):
        params = {}
        if category: params['category__code'] = category
        if is_system is not None: params['is_system'] = is_system
        return self._make_request("GET", "parameters/", params=params)

    def get_parameter_values(self, context_type, context_id):
        return self._make_request("GET", "parameters/values/", params={'context_type': context_type, 'context_id': context_id})

    def set_parameter_value(self, parameter_id, context_type, context_id, value):
        return self._make_request("POST", "parameters/values/", {'parameter': parameter_id, 'context_type': context_type, 'context_id': context_id, 'value': value})

    # -----------------------------------------------------------------------
    # MATERIAUX
    # -----------------------------------------------------------------------

    def get_concrete_classes(self, min_fck=None, norm_code=None, active=True):
        params = {'is_active': active}
        if min_fck is not None: params['fck__gte'] = min_fck
        if norm_code: params['norm__code'] = norm_code
        return self._make_request("GET", "materials/concrete/", params=params)

    def get_steel_classes(self, min_fyk=None, norm_code=None, active=True):
        params = {'is_active': active}
        if min_fyk is not None: params['fyk__gte'] = min_fyk
        if norm_code: params['norm__code'] = norm_code
        return self._make_request("GET", "materials/steel/", params=params)

    def get_rebar_diameters(self, steel_class=None):
        params = {}
        if steel_class: params['steel_class__designation'] = steel_class
        return self._make_request("GET", "materials/bars/", params=params)

    # -----------------------------------------------------------------------
    # SECTIONS
    # -----------------------------------------------------------------------

    def get_sections(self, family=None, material=None, active=True):
        params = {'is_active': active}
        if family: params['family__code'] = family
        if material: params['material'] = material
        return self._make_request("GET", "sections/", params=params)

    def recommend_section(self, span, load, element_type):
        return self._make_request("POST", "sections/recommend/", {'span': span, 'load': load, 'element_type': element_type})

    # -----------------------------------------------------------------------
    # EXPOSITION
    # -----------------------------------------------------------------------

    def get_exposure_classes(self, norm_code=None):
        params = {}
        if norm_code: params['norm__code'] = norm_code
        return self._make_request("GET", "exposure/classes/", params=params)

    def get_cover_requirements(self, exposure_class_code, element_type=None):
        params = {'exposure_class': exposure_class_code}
        if element_type: params['element_type'] = element_type
        return self._make_request("GET", "exposure/cover/", params=params)

    # -----------------------------------------------------------------------
    # REGLES
    # -----------------------------------------------------------------------

    def get_rules(self, element_type=None, category=None, active=True):
        params = {'is_active': active}
        if element_type: params['element_type'] = element_type
        if category: params['category__code'] = category
        return self._make_request("GET", "rules/", params=params)

    def evaluate_rule(self, rule_id, context):
        return self._make_request("POST", "rules/" + str(rule_id) + "/evaluate/", context)

    def get_ruleset(self, ruleset_code):
        return self._make_request("GET", "rules/sets/" + str(ruleset_code) + "/")

    # -----------------------------------------------------------------------
    # ACTIONS
    # -----------------------------------------------------------------------

    def get_actions(self, category=None, active=True):
        params = {'is_active': active}
        if category: params['category__code'] = category
        return self._make_request("GET", "actions/", params=params)

    def get_action_detail(self, action_code):
        return self._make_request("GET", "actions/" + str(action_code) + "/")

    def log_action_execution(self, project_id, action_code, status, duration, details=None):
        return self._make_request("POST", "actions/log/", {'project': project_id, 'action_code': action_code, 'status': status, 'duration': duration, 'details': details or {}})

    # -----------------------------------------------------------------------
    # WORKFLOWS
    # -----------------------------------------------------------------------

    def get_workflows(self, category=None, active=True):
        params = {'is_active': active}
        if category: params['category__code'] = category
        return self._make_request("GET", "workflows/", params=params)

    def get_workflow_detail(self, workflow_code):
        return self._make_request("GET", "workflows/" + str(workflow_code) + "/")

    def get_workflow_steps(self, workflow_code):
        return self._make_request("GET", "workflows/" + str(workflow_code) + "/steps/")

    # -----------------------------------------------------------------------
    # CHARGES
    # -----------------------------------------------------------------------

    def get_load_types(self, category=None, norm_code=None):
        params = {}
        if category: params['category__code'] = category
        if norm_code: params['norm__code'] = norm_code
        return self._make_request("GET", "loads/types/", params=params)

    def get_load_combinations(self, project_id=None, norm_code=None, limit_state=None):
        params = {}
        if project_id: params['project'] = project_id
        if norm_code: params['norm__code'] = norm_code
        if limit_state: params['limit_state'] = limit_state
        return self._make_request("GET", "loads/combinations/", params=params)

    def get_project_loads(self, project_id):
        return self._make_request("GET", "loads/cases/", params={'project': project_id})

    def create_load_case(self, project_id, load_data):
        load_data['project'] = project_id
        return self._make_request("POST", "loads/cases/", load_data)

    # -----------------------------------------------------------------------
    # TEMPLATES
    # -----------------------------------------------------------------------

    def get_view_templates(self, template_type=None):
        params = {}
        if template_type: params['view_type'] = template_type
        return self._make_request("GET", "templates/views/", params=params)

    def get_schedule_templates(self, category=None):
        params = {}
        if category: params['category'] = category
        return self._make_request("GET", "templates/schedules/", params=params)

    def get_sheet_templates(self):
        return self._make_request("GET", "templates/sheets/")

    # -----------------------------------------------------------------------
    # FORMULES
    # -----------------------------------------------------------------------

    def get_formulas(self, category=None):
        params = {}
        if category: params['category__code'] = category
        return self._make_request("GET", "formulas/", params=params)

    def evaluate_formula(self, formula_code, variables):
        return self._make_request("POST", "formulas/" + str(formula_code) + "/evaluate/", {'variables': variables})

    # -----------------------------------------------------------------------
    # LOGS
    # -----------------------------------------------------------------------

    def send_log(self, project_id, action_type, detail, status='success', message='', element_id=None, execution_time=None):
        log_data = {'project': project_id, 'action_type': action_type, 'action_detail': detail, 'status': status, 'message': message}
        if element_id is not None: log_data['element_id'] = element_id
        if execution_time is not None: log_data['execution_time'] = execution_time
        try:
            return self._make_request("POST", "logs/", log_data)
        except Exception as e:
            print("Warning: Echec envoi log : " + str(e))
            return None

    def send_error_log(self, error_type, error_message, stack_trace='', project_id=None, context=None):
        error_data = {'error_type': error_type, 'error_message': str(error_message), 'stack_trace': stack_trace, 'context': context or {}}
        if project_id: error_data['project'] = project_id
        try:
            return self._make_request("POST", "logs/errors/", error_data)
        except Exception as e:
            print("Warning: Echec envoi error log : " + str(e))
            return None

    # -----------------------------------------------------------------------
    # UI
    # -----------------------------------------------------------------------

    def get_panels(self, active=True):
        return self._make_request("GET", "ui/panels/", params={'is_active': active})

    def get_panel_buttons(self, panel_code):
        return self._make_request("GET", "ui/panels/" + str(panel_code) + "/buttons/")

    # -----------------------------------------------------------------------
    # UTILITAIRES
    # -----------------------------------------------------------------------

    def set_offline_mode(self, enabled):
        self.offline_mode = enabled
        print("Info: Mode offline " + ("active" if enabled else "desactive"))

    def ping(self):
        return self.test_connection()

    def __str__(self):
        return ("<APIClient url=" + str(self.base_url) +
                " authenticated=" + str(self.session_token is not None) +
                " has_refresh=" + str(self.refresh_token is not None) +
                " offline=" + str(self.offline_mode) + ">")

    def __repr__(self):
        return self.__str__()