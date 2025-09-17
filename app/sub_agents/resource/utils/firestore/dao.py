import os
from typing import Any, Dict, Optional, List

from google.cloud import firestore

# Read Firestore project from env
FIRESTORE_PROJECT = os.getenv("FIRESTORE_PROJECT")
if not FIRESTORE_PROJECT:
    raise RuntimeError("Environment variable FIRESTORE_PROJECT must be set.")

def create_firestore_database() -> firestore.Client:
    """
    Initialize and return a Firestore client.
    """
    return firestore.Client(project=FIRESTORE_PROJECT)


_client = create_firestore_database()


def create_document(
    collection: str,
    document: Dict[str, Any],
    document_id: Optional[str] = None,
) -> str:
    """
    Create a new document in the given collection.

    Args:
        collection: Firestore collection name.
        document: Data to store.
        document_id: If provided, use this ID; otherwise Firestore will auto-generate one.

    Returns:
        The document ID of the newly created document.
    """
    col_ref = _client.collection(collection)
    if document_id:
        doc_ref = col_ref.document(document_id)
        doc_ref.set(document)
        return document_id
    else:
        doc_ref, _ = col_ref.add(document)
        return doc_ref.id


def get_document(
    collection: str,
    document_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch a document by ID.

    Args:
        collection: Firestore collection name.
        document_id: ID of the document to retrieve.

    Returns:
        The document data as a dict, or None if not found.
    """
    doc_ref = _client.collection(collection).document(document_id)
    snapshot = doc_ref.get()
    if snapshot.exists:
        return snapshot.to_dict()
    else:
        return None


def update_document(
    collection: str,
    document_id: str,
    new_document: Dict[str, Any],
) -> None:
    """
    Overwrite an existing document with new data.

    Args:
        collection: Firestore collection name.
        document_id: ID of the document to overwrite.
        new_document: The new data dict.
    """
    doc_ref = _client.collection(collection).document(document_id)
    doc_ref.set(new_document)


def delete_document(
    collection: str,
    document_id: str,
) -> None:
    """
    Delete a document by ID.

    Args:
        collection: Firestore collection name.
        document_id: ID of the document to delete.
    """
    doc_ref = _client.collection(collection).document(document_id)
    doc_ref.delete()


def update_document_field(
    collection: str,
    document_id: str,
    field_name: str,
    new_value: Any,
) -> None:
    """
    Update a single field of a document.

    Args:
        collection: Firestore collection name.
        document_id: ID of the document to update.
        field_name: The field to update (dot-notation for nested fields allowed).
        new_value: The new value for the field.
    """
    doc_ref = _client.collection(collection).document(document_id)
    doc_ref.update({field_name: new_value})



def get_all_documents(
    collection: str,
    include_ids: bool = True,
) -> List[Dict[str, Any]]:
    """
    Retrieve all documents in a collection.

    Args:
        collection: Firestore collection name.
        include_ids: If True, include each document's ID under key 'id'.

    Returns:
        A list of document dicts (empty list if none found).
    """
    col_ref = _client.collection(collection)
    docs: List[Dict[str, Any]] = []
    for snap in col_ref.stream():
        data = snap.to_dict() or {}
        if include_ids:
            data = {"id": snap.id, **data}
        docs.append(data)
    return docs