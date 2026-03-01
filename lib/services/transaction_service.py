# -*- coding: utf-8 -*-
"""
TransactionService - Service de gestion des transactions Revit
==============================================================
Responsabilites :
- Creation et gestion des transactions
- Context manager pour transactions
- Groupes de transactions
- Gestion des erreurs et rollback

Auteur : AutoRevit Team
Date : 2025
"""

from utils.logger import get_logger

logger = get_logger(__name__)

# Exceptions personnalisees
class RevitAPIError(Exception):
    """Exception levee quand Revit API n'est pas disponible"""
    pass

class TransactionError(Exception):
    """Exception levee lors d'erreurs de transaction"""
    pass


# Imports Revit API (avec gestion si hors Revit)
try:
    from Autodesk.Revit.DB import (
        Transaction,
        TransactionGroup,
        SubTransaction,
        FailureHandlingOptions,
        FailureHandler,
        Document
    )
    REVIT_AVAILABLE = True
except ImportError:
    
    REVIT_AVAILABLE = False
    
    # Classes factices pour mode developpement
    class Transaction:
        def __init__(self, doc, name):
            self.doc = doc
            self.name = name
            self.has_started = False
        
        def Start(self):
            self.has_started = True
            return True
        
        def Commit(self):
            return True
        
        def RollBack(self):
            return True
        
        def HasStarted(self):
            return self.has_started
        
        def GetName(self):
            return self.name
    
    class TransactionGroup:
        def __init__(self, doc, name):
            self.doc = doc
            self.name = name
        
        def Start(self):
            return True
        
        def Commit(self):
            return True
        
        def RollBack(self):
            return True
    
    class SubTransaction:
        def __init__(self, doc):
            self.doc = doc
        
        def Start(self):
            return True
        
        def Commit(self):
            return True
        
        def RollBack(self):
            return True


class TransactionService:
    """
    Service de gestion des transactions Revit.
    
    Exemple d'utilisation :
    ----------------------
    >>> from pyrevit import revit
    >>> from services import TransactionService
    >>>
    >>> doc = revit.doc
    >>> tx_svc = TransactionService(doc)
    >>>
    >>> # Utilisation comme context manager
    >>> with tx_svc.start("Creation poteaux"):
    >>>     # Operations Revit
    >>>     pass
    >>>
    >>> # Transaction manuelle
    >>> tx_svc.start_transaction("Modification")
    >>> try:
    >>>     # Operations
    >>>     tx_svc.commit()
    >>> except:
    >>>     tx_svc.rollback()
    """

    def __init__(self, document):
        if not REVIT_AVAILABLE:
            raise RevitAPIError("Revit API non disponible")
        
        self.doc = document
        self.current_transaction = None
        self.current_group = None
        self.current_subtransaction = None
        self.transaction_count = 0
        self.transaction_history = []
        
        logger.info("TransactionService initialise")
    
    # ========================================================================
    # TRANSACTIONS SIMPLES
    # ========================================================================
    
    def start_transaction(self, name="AutoRevit Operation"):
        """
        Demarre une nouvelle transaction.
        
        Args:
            name (str): Nom de la transaction
        
        Returns:
            Transaction: Transaction demarree
        """
        try:
            if self.current_transaction and self.current_transaction.HasStarted():
                logger.warning("Transaction deja en cours")
                return self.current_transaction
            
            transaction = Transaction(self.doc, name)
            transaction.Start()
            
            self.current_transaction = transaction
            self.transaction_count += 1
            
            logger.info("Transaction demarree: " + name)
            return transaction
        
        except Exception as e:
            logger.error("Erreur start_transaction: " + str(e))
            raise TransactionError("Impossible de demarrer transaction: " + str(e))
    
    def commit_transaction(self):
        """
        Valide la transaction courante.
        
        Returns:
            bool: True si reussi
        """
        try:
            if not self.current_transaction:
                logger.warning("Aucune transaction en cours")
                return False
            
            if not self.current_transaction.HasStarted():
                logger.warning("Transaction non demarree")
                return False
            
            result = self.current_transaction.Commit()
            
            if result:
                logger.info("Transaction validee: " + self.current_transaction.GetName())
                self._add_to_history(self.current_transaction, "commit")
                self.current_transaction = None
                return True
            else:
                logger.error("Echec validation transaction")
                return False
        
        except Exception as e:
            logger.error("Erreur commit_transaction: " + str(e))
            raise TransactionError("Impossible de valider transaction: " + str(e))
    
    def rollback_transaction(self):
        """
        Annule la transaction courante.
        
        Returns:
            bool: True si reussi
        """
        try:
            if not self.current_transaction:
                logger.warning("Aucune transaction en cours")
                return False
            
            if not self.current_transaction.HasStarted():
                logger.warning("Transaction non demarree")
                return False
            
            result = self.current_transaction.RollBack()
            
            logger.info("Transaction annulee: " + self.current_transaction.GetName())
            self._add_to_history(self.current_transaction, "rollback")
            self.current_transaction = None
            return True
        
        except Exception as e:
            logger.error("Erreur rollback_transaction: " + str(e))
            raise TransactionError("Impossible d'annuler transaction: " + str(e))
    
    # ========================================================================
    # GROUPES DE TRANSACTIONS
    # ========================================================================
    
    def start_group(self, name="AutoRevit Group"):
        """
        Demarre un groupe de transactions.
        
        Args:
            name (str): Nom du groupe
        
        Returns:
            TransactionGroup: Groupe demarre
        """
        try:
            if self.current_group:
                logger.warning("Groupe deja en cours")
                return self.current_group
            
            group = TransactionGroup(self.doc, name)
            group.Start()
            
            self.current_group = group
            logger.info("Groupe demarre: " + name)
            return group
        
        except Exception as e:
            logger.error("Erreur start_group: " + str(e))
            raise TransactionError("Impossible de demarrer groupe: " + str(e))
    
    def commit_group(self):
        """
        Valide le groupe courant.
        
        Returns:
            bool: True si reussi
        """
        try:
            if not self.current_group:
                logger.warning("Aucun groupe en cours")
                return False
            
            result = self.current_group.Commit()
            
            if result:
                logger.info("Groupe valide")
                self.current_group = None
                return True
            else:
                logger.error("Echec validation groupe")
                return False
        
        except Exception as e:
            logger.error("Erreur commit_group: " + str(e))
            raise TransactionError("Impossible de valider groupe: " + str(e))
    
    def rollback_group(self):
        """
        Annule le groupe courant.
        
        Returns:
            bool: True si reussi
        """
        try:
            if not self.current_group:
                logger.warning("Aucun groupe en cours")
                return False
            
            result = self.current_group.RollBack()
            
            logger.info("Groupe annule")
            self.current_group = None
            return True
        
        except Exception as e:
            logger.error("Erreur rollback_group: " + str(e))
            raise TransactionError("Impossible d'annuler groupe: " + str(e))
    
    # ========================================================================
    # SUBTRANSACTIONS
    # ========================================================================
    
    def start_subtransaction(self):
        """
        Demarre une subtransaction.
        
        Returns:
            SubTransaction: Subtransaction demarree
        """
        try:
            if not self.current_transaction:
                logger.error("Subtransaction requiert transaction parente")
                return None
            
            sub = SubTransaction(self.doc)
            sub.Start()
            
            self.current_subtransaction = sub
            logger.info("Subtransaction demarree")
            return sub
        
        except Exception as e:
            logger.error("Erreur start_subtransaction: " + str(e))
            raise TransactionError("Impossible de demarrer subtransaction: " + str(e))
    
    def commit_subtransaction(self):
        """
        Valide la subtransaction courante.
        
        Returns:
            bool: True si reussi
        """
        try:
            if not self.current_subtransaction:
                logger.warning("Aucune subtransaction en cours")
                return False
            
            result = self.current_subtransaction.Commit()
            
            if result:
                logger.info("Subtransaction validee")
                self.current_subtransaction = None
                return True
            else:
                logger.error("Echec validation subtransaction")
                return False
        
        except Exception as e:
            logger.error("Erreur commit_subtransaction: " + str(e))
            raise TransactionError("Impossible de valider subtransaction: " + str(e))
    
    def rollback_subtransaction(self):
        """
        Annule la subtransaction courante.
        
        Returns:
            bool: True si reussi
        """
        try:
            if not self.current_subtransaction:
                logger.warning("Aucune subtransaction en cours")
                return False
            
            result = self.current_subtransaction.RollBack()
            
            logger.info("Subtransaction annulee")
            self.current_subtransaction = None
            return True
        
        except Exception as e:
            logger.error("Erreur rollback_subtransaction: " + str(e))
            raise TransactionError("Impossible d'annuler subtransaction: " + str(e))
    
    # ========================================================================
    # CONTEXT MANAGER
    # ========================================================================
    
    def start(self, name="AutoRevit Operation", as_group=False):
        """
        Demarre un contexte de transaction.
        
        Args:
            name (str): Nom de la transaction
            as_group (bool): Utiliser TransactionGroup
        
        Returns:
            TransactionContext: Contexte
        """
        return TransactionContext(self, name, as_group)
    
    # ========================================================================
    # UTILITAIRES
    # ========================================================================
    
    def is_transaction_active(self):
        """
        Verifie si une transaction est active.
        
        Returns:
            bool: True si transaction active
        """
        return (self.current_transaction and 
                self.current_transaction.HasStarted())
    
    def get_current_transaction_name(self):
        """
        Recupere le nom de la transaction courante.
        
        Returns:
            str: Nom ou None
        """
        if self.current_transaction:
            return self.current_transaction.GetName()
        return None
    
    def _add_to_history(self, transaction, action):
        """Ajoute une transaction a l'historique."""
        self.transaction_history.append({
            'name': transaction.GetName(),
            'action': action,
            'timestamp': self._get_timestamp()
        })
        
        # Limiter taille historique
        if len(self.transaction_history) > 100:
            self.transaction_history = self.transaction_history[-100:]
    
    def _get_timestamp(self):
        """Retourne timestamp pour historique."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_transaction_history(self):
        """
        Recupere l'historique des transactions.
        
        Returns:
            list: Historique
        """
        return self.transaction_history


class TransactionContext:
    """
    Context manager pour transactions Revit.
    
    Exemple:
    >>> with TransactionService(doc).start("Operation") as tx:
    >>>     # Code Revit
    >>>     pass
    """
    
    def __init__(self, service, name, as_group=False):
        self.service = service
        self.name = name
        self.as_group = as_group
        self.transaction = None
    
    def __enter__(self):
        if self.as_group:
            self.transaction = self.service.start_group(self.name)
        else:
            self.transaction = self.service.start_transaction(self.name)
        return self.transaction
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Erreur -> rollback
            if self.as_group:
                self.service.rollback_group()
            else:
                self.service.rollback_transaction()
            logger.error("Transaction annulee: " + str(exc_val))
            return False
        else:
            # Succes -> commit
            if self.as_group:
                self.service.commit_group()
            else:
                self.service.commit_transaction()
            return True


# ============================================================================
# FONCTION DE TEST
# ============================================================================

def test_transaction_service():
    print("\n" + "="*60)
    print("TEST TRANSACTION SERVICE")
    print("="*60)
    
    try:
        from pyrevit import revit
        doc = revit.doc
        
        if not doc:
            print("Aucun document Revit ouvert")
            return
        
        print("\n1 Creation TransactionService...")
        tx_svc = TransactionService(doc)
        
        # Test transaction simple
        print("\n2 Test transaction simple...")
        tx_svc.start_transaction("Test Transaction")
        print("   Transaction demarree")
        tx_svc.commit_transaction()
        print("   Transaction validee")
        
        # Test context manager
        print("\n3 Test context manager...")
        with tx_svc.start("Test Context") as tx:
            print("   Transaction context: " + tx.GetName())
        print("   Context termine")
        
        # Test historique
        print("\n4 Test historique...")
        history = tx_svc.get_transaction_history()
        print("   " + str(len(history)) + " transactions dans historique")
        
        print("\n" + "="*60)
        print("TOUS LES TESTS PASSES")
        print("="*60 + "\n")
    
    except Exception as e:
        print("\nERREUR: " + str(e))
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_transaction_service()