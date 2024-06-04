# from datetime import datetime
import logging
from operator import or_, and_
from typing import Optional, List

from backend.auth.jwt import min_role_required
from backend.mixpanel.mix import track_to_mp
from mixpanel import MixpanelException
from backend.database.models.user import UserRole
from backend.database.models.employment import (
    Employment,
    merge_employment_records
)
from backend.database.models.officer import OfficerJoinView, OfficerJoinModel
from backend.database.models.agency import Agency
from flask import Blueprint, abort, jsonify, request
from flask_jwt_extended.view_decorators import jwt_required
from pydantic import BaseModel

from ..database import Officer, db
from ..schemas import (
    CreateOfficerSchema,
    officer_orm_to_json,
    officer_to_orm,
    employment_to_orm,
    employment_orm_to_json,
    validate,
)


bp = Blueprint("officer_routes", __name__, url_prefix="/api/v1/officers")


class SearchOfficerSchema(BaseModel):
    name: Optional[str] = None
    agency: Optional[str] = None
    badgeNumber: Optional[str] = None
    location: Optional[str] = None
    page: Optional[int] = 1
    perPage: Optional[int] = 20

    class Config:
        extra = "forbid"
        schema_extra = {
            "example": {
                "officerName": "John Doe",
                "location" : "New York",
                "badgeNumber" : 1234,
                "page": 1,
                "perPage": 20,
            }
        }


class AddEmploymentSchema(BaseModel):
    agency_id: int
    badge_number: str
    officer_id: Optional[int]
    highest_rank: Optional[str]
    earliest_employment: Optional[str]
    latest_employment: Optional[str]
    unit: Optional[str]
    currently_employed: bool = True


class AddEmploymentListSchema(BaseModel):
    agencies: List[AddEmploymentSchema]


# Search for an officer or group of officers
@bp.route("/search", methods=["POST"])
@jwt_required()
@min_role_required(UserRole.PUBLIC)
@validate(json=SearchOfficerSchema)
def search_officer():
    """Search Officers"""
    body: SearchOfficerSchema = request.context.json
    query = db.session.query('Officer')
    logger = logging.getLogger("officers")

    try:
        if body.name:
            names = body.officerName.split()
            if len(names) == 1:
                query = Officer.query.filter(
                    or_(
                        Officer.first_name.ilike(f"%{body.officerName}%"),
                        Officer.last_name.ilike(f"%{body.officerName}%")
                    )
                )
            elif len(names) == 2:
                query = Officer.query.filter(
                    or_(
                        Officer.first_name.ilike(f"%{names[0]}%"),
                        Officer.last_name.ilike(f"%{names[1]}%")
                    )
                )
            else:
                query = Officer.query.filter(
                    or_(
                        Officer.first_name.ilike(f"%{names[0]}%"),
                        Officer.middle_name.ilike(f"%{names[1]}%"),
                        Officer.last_name.ilike(f"%{names[2]}%")
                    )
                )

        if body.badgeNumber:
            officer_ids = [
                result.officer_id for result in db.session.query(
                    Employment
                    ).filter_by(badge_number=body.badgeNumber).all()
            ]
            query = Officer.query.filter(Officer.id.in_(officer_ids)).all()

    except Exception as e:
        abort(422, description=str(e))

    results = query.paginate(
        page=body.page, per_page=body.perPage, max_per_page=100
    )

    try:
        track_to_mp(request, "search_officer", {
            "officername": body.officerName,
            "badgeNumber": body.badgeNumber
        })
    except MixpanelException as e:
        logger.error(e)
    try:
        return {
            "results": [
                officer_orm_to_json(result) for result in results.items
            ],
            "page": results.page,
            "totalPages": results.pages,
            "totalResults": results.total,
        }
    except Exception as e:
        abort(500, description=str(e))


# Create an officer profile
@bp.route("/", methods=["POST"])
@jwt_required()
@min_role_required(UserRole.CONTRIBUTOR)
@validate(json=CreateOfficerSchema)
def create_officer():
    """Create an officer profile.
    """

    try:
        officer = officer_to_orm(request.context.json)
    except Exception as e:
        abort(400, description=str(e))

    created = officer.create()

    track_to_mp(
        request,
        "create_officer",
        {
            "officer_id": officer.id
        },
    )
    return officer_orm_to_json(created)


# Get an officer profile
@bp.route("/<int:officer_id>", methods=["GET"])
@jwt_required()
@min_role_required(UserRole.PUBLIC)
@validate()
def get_officer(officer_id: int):
    """Get an officer profile.
    """
    officer = db.session.query(Officer).get(officer_id)
    if officer is None:
        abort(404, description="Officer not found")
    return officer_orm_to_json(officer)


# Get all officers
@bp.route("/", methods=["GET"])
@jwt_required()
@min_role_required(UserRole.PUBLIC)
@validate()
def get_all_officers():
    """Get all officers.
    Accepts Query Parameters for pagination:
    per_page: number of results per page
    page: page number
    """
    args = request.args
    q_page = args.get("page", 1, type=int)
    q_per_page = args.get("per_page", 20, type=int)

    all_officers = db.session.query(Officer)
    pagination = all_officers.paginate(
        page=q_page, per_page=q_per_page, max_per_page=100
    )

    return {
        "results": [
            officer_orm_to_json(officer) for officer in pagination.items],
        "page": pagination.page,
        "totalPages": pagination.pages,
        "totalResults": pagination.total,
    }


# Update an officer profile
@bp.route("/<int:officer_id>", methods=["PUT"])
@jwt_required()
@min_role_required(UserRole.CONTRIBUTOR)
@validate(json=CreateOfficerSchema)
def update_officer(officer_id: int):
    """Update an officer profile.
    """
    officer = db.session.query(Officer).get(officer_id)
    if officer is None:
        abort(404, description="Officer not found")

    try:
        officer.update(request.context.json)
    except Exception as e:
        abort(400, description=str(e))

    track_to_mp(
        request,
        "update_officer",
        {
            "officer_id": officer.id
        },
    )
    return officer_orm_to_json(officer)


# Delete an officer profile
@bp.route("/<int:officer_id>", methods=["DELETE"])
@jwt_required()
@min_role_required(UserRole.ADMIN)
@validate()
def delete_officer(officer_id: int):
    """Delete an officer profile.
    Must be an admin to delete an officer.
    """
    officer = db.session.query(Officer).get(officer_id)
    if officer is None:
        abort(404, description="Officer not found")
    try:
        db.session.delete(officer)
        db.session.commit()
        track_to_mp(
            request,
            "delete_officer",
            {
                "officer_id": officer.id
            },
        )
        return {"message": "Officer deleted successfully"}
    except Exception as e:
        abort(400, description=str(e))


# Update an officer's employment history
@bp.route("/<int:officer_id>/employment", methods=["PUT"])
@jwt_required()
@min_role_required(UserRole.CONTRIBUTOR)
@validate(json=AddEmploymentListSchema)
def update_employment(officer_id: int):
    """Update an officer's employment history.
    Must be a contributor to update an officer's employment history.
    May include multiple records in the request body.
    """
    officer = db.session.query(Officer).get(officer_id)
    if officer is None:
        abort(404, description="Officer not found")

    records = request.context.json.agencies

    created = []
    failed = []
    for record in records:
        try:
            agency = db.session.query(Agency).get(
                record.agency_id)
            if agency is None:
                failed.append({
                    "agency_id": record.agency_id,
                    "reason": "Agency not found"
                })
            else:
                employments = db.session.query(Employment).filter(
                    and_(
                        and_(
                            Employment.officer_id == officer_id,
                            Employment.agency_id == record.agency_id
                        ),
                        Employment.badge_number == record.badge_number
                    )
                )
                if employments is not None:
                    # If the officer already has a records for this agency,
                    # we need to update the earliest and latest employment dates
                    employment = employment_to_orm(record)
                    employment.officer_id = officer_id
                    employment = merge_employment_records(
                        employments.all() + [employment],
                        unit=record.unit,
                        currently_employed=record.currently_employed
                    )

                    # Delete the old records and replace them with the new one
                    employments.delete()
                    created.append(employment.create())
                else:
                    record.officer_id = officer_id
                    employment = employment_to_orm(record)
                    created.append(employment.create())
                # Commit before iterating to the next record
                db.session.commit()
        except Exception as e:
            failed.append({
                "agency_id": record.agency_id,
                "reason": str(e)
            })

    track_to_mp(
        request,
        "update_employment",
        {
            "officer_id": officer.id,
            "agencies_added": len(created),
            "agencies_failed": len(failed)
        },
    )
    try:
        return {
            "created": [
                employment_orm_to_json(item) for item in created],
            "failed": failed,
            "totalCreated": len(created),
            "totalFailed": len(failed),
        }
    except Exception as e:
        abort(400, description=str(e))


# Retrieve an officer's employment history
@bp.route("/<int:officer_id>/employment", methods=["GET"])
@jwt_required()
@min_role_required(UserRole.PUBLIC)
@validate()
def get_employment(officer_id: int):
    """Retrieve an officer's employment history.
    """
    args = request.args
    q_page = args.get("page", 1, type=int)
    q_per_page = args.get("per_page", 20, type=int)

    officer = db.session.query(Officer).get(officer_id)
    if officer is None:
        abort(404, description="Officer not found")

    try:
        employments = db.session.query(Employment).filter(
            Employment.officer_id == officer_id)

        pagination = employments.paginate(
            page=q_page, per_page=q_per_page, max_per_page=100
        )

        return {
            "results": [
                employment_orm_to_json(
                    employment) for employment in pagination.items],
            "page": pagination.page,
            "totalPages": pagination.pages,
            "totalResults": pagination.total,
        }
    except Exception as e:
        abort(400, description=str(e))


DEFAULT_PER_PAGE = 5

"""
API endpoint to allow searching officer information
by State.
"""


@jwt_required()
@min_role_required(UserRole.PUBLIC)
@bp.route("/search_wlocation", methods=["POST"])
def search_state():
    # get request parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', DEFAULT_PER_PAGE))
    search_term = request.args.get('search_term')
    # query to search for relevant officers on the joined view
    query = db.session.query(
        db.distinct(OfficerJoinView.id),
        OfficerJoinView.officer_first_name,
        OfficerJoinView.officer_middle_name,
        OfficerJoinView.officer_last_name,
        OfficerJoinView.officer_date_of_birth,
        OfficerJoinView.stateID_state,
        OfficerJoinView.stateID_value,
        db.func.max(db.func.full_text.ts_rank(
            db.func.setweight(
                db.func.coalesce(
                    OfficerJoinView.tsv_stateID_state, ''), 'A')
            , db.func.to_tsquery(
                        search_term,
                        postgresql_regconfig='english'
                        )
        )).label('rank')
    ).filter(db.or_(
        OfficerJoinView.tsv_stateID_state.match(
            search_term,
            postgresql_regconfig='english'),
    )).group_by(
        OfficerJoinView.id,
        OfficerJoinView.officer_first_name,
        OfficerJoinView.officer_middle_name,
        OfficerJoinView.officer_last_name,
        OfficerJoinView.officer_date_of_birth,
        OfficerJoinView.stateID_state,
        OfficerJoinView.stateID_value
    ).order_by(db.text('rank DESC')).all()
    # returning results and pagination
    results = []
    for search_result in query:
        result_dict = {
                "first_name" : search_result.officer_first_name,
                "middle_name" : search_result.officer_middle_name,
                "last_name" : search_result.officer_last_name,
                "date_of_birth" : search_result.officer_date_of_birth,
                "stateID_state" : search_result.stateID_state,
                "stateID_value" : search_result.stateID_value,
        }
        results.append(result_dict)
    start_index = (page - 1) * per_page
    end_index = min(start_index + per_page, len(results))
    paginated_results = results[start_index:end_index]
    response = {
                "page": page,
                "per_page": per_page,
                "total_results": len(results),
                "results": paginated_results
        }
    try:
        return jsonify(response)
    except Exception as e:
        return (500, str(e))


"""
API to add to Joined Model
"""


# @jwt_required()
# @min_role_required(UserRole.PUBLIC)
# @bp.route("/addOfficerJoin", methods=["POST"])
# def addOfficerJoined():

#     body = request.get_json()
#     # assume body is not None while validating
#     officer_first_name = body['officer_first_name']
#     officer_middle_name = body['officer_middle_name']
#     officer_last_name = body['officer_last_name']
#     officer_date_of_birth = body['officer_date_of_birth']
#     stateID_state = body['stateID_state']
#     stateID_value = body['stateID_value']

#     try:
#         officer_date_of_birth = datetime.strptime(
#             officer_date_of_birth,
#             '%Y-%m-%d').date()
#     except ValueError:
#         return jsonify(
#             {"error": "Invalid date format, should be YYYY-MM-DD"}
#             ), 400
#     if not all([officer_first_name,
#                 officer_last_name,
#                 officer_date_of_birth,
#                 stateID_state,
#                 stateID_value]):
#         return jsonify({"error": "Missing required fields"}), 400

#     new_officer = OfficerJoinModel(
#         officer_first_name=officer_first_name,
#         officer_middle_name=officer_middle_name,
#         officer_last_name=officer_last_name,
#         officer_date_of_birth=officer_date_of_birth,
#         stateID_state=stateID_state,
#         stateID_value=stateID_value
#     )

#     db.session.add(new_officer)
#     db.session.commit()

#     return {
#         "message": "Officer Joined Model instance added successfully"
#     }, 201

"""
Search API for testing purpose
Interacts with the OfficerJoin Model View directly
instead of interacting with the Materialized View
"""


@jwt_required()
@min_role_required(UserRole.PUBLIC)
@bp.route("/search_wlocation_test", methods=["POST"])
def search_state_test():
    # get request parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', DEFAULT_PER_PAGE))
    search_term = request.args.get('search_term')
    # query to search for relevant officers on the joined view
    query = db.session.query(
        db.distinct(OfficerJoinModel.id),
        OfficerJoinModel.officer_first_name,
        OfficerJoinModel.officer_middle_name,
        OfficerJoinModel.officer_last_name,
        OfficerJoinModel.officer_date_of_birth,
        OfficerJoinModel.stateID_state,
        OfficerJoinModel.stateID_value,
        db.func.max(db.func.full_text.ts_rank(
            db.func.setweight(
                db.func.coalesce(
                    OfficerJoinModel.tsv_stateID_state, ''), 'A')
            , db.func.to_tsquery(
                        search_term,
                        postgresql_regconfig='english'
                        )
        )).label('rank')
    ).filter(db.or_(
        OfficerJoinModel.tsv_stateID_state.match(
            search_term,
            postgresql_regconfig='english'),
    )).group_by(
        OfficerJoinModel.id,
        OfficerJoinModel.officer_first_name,
        OfficerJoinModel.officer_middle_name,
        OfficerJoinModel.officer_last_name,
        OfficerJoinModel.officer_date_of_birth,
        OfficerJoinModel.stateID_state,
        OfficerJoinModel.stateID_value
    ).order_by(db.text('rank DESC')).all()
    # returning results and pagination
    results = []
    for search_result in query:
        result_dict = {
                "first_name" : search_result.officer_first_name,
                "middle_name" : search_result.officer_middle_name,
                "last_name" : search_result.officer_last_name,
                "date_of_birth" : search_result.officer_date_of_birth,
                "stateID_state" : search_result.stateID_state,
                "stateID_value" : search_result.stateID_value,
        }
        results.append(result_dict)
    start_index = (page - 1) * per_page
    end_index = min(start_index + per_page, len(results))
    paginated_results = results[start_index:end_index]
    response = {
                "page": page,
                "per_page": per_page,
                "total_results": len(query),
                "results": paginated_results
        }
    try:
        return jsonify(response)
    except Exception as e:
        return (500, str(e))
