from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import uuid
from pathlib import Path
import io
import time

app = FastAPI(title="DSS-TRACK: Semantic Duplicate Detection API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model variable
model = None


@app.on_event("startup")
async def load_model():
    """Load the sentence transformer model at startup with retry logic"""
    global model
    max_retries = 3
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            print(
                f"Loading sentence transformer model (attempt {attempt + 1}/{max_retries})..."
            )
            model = SentenceTransformer(
                "sentence-transformers/all-MiniLM-L6-v2", token=False
            )
            print("Model loaded successfully!")
            return
        except Exception as e:
            print(
                f"Failed to load model (attempt {attempt + 1}/{max_retries}): {str(e)}"
            )
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print(
                    "ERROR: Failed to load model after all retries. Application may not function correctly."
                )
                # Don't crash the app - let it start and fail gracefully on API calls


# In-memory storage for sessions
sessions = {}


# Data models
class ColumnSelection(BaseModel):
    session_id: str
    columns: List[str]
    similarity_threshold: float = 0.85


class DuplicateReview(BaseModel):
    session_id: str
    duplicate_id: str
    is_duplicate: bool


class SessionData:
    def __init__(self, session_id: str, df: pd.DataFrame, filename: str):
        self.session_id = session_id
        self.original_df = df.copy()
        self.filename = filename
        self.selected_columns = []
        self.duplicate_groups = []
        self.reviewed_duplicates = {}
        self.embeddings = None
        self.similarity_threshold = 0.85


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a CSV or Excel file"""
    try:
        # Validate file type
        if not (
            file.filename.endswith(".csv")
            or file.filename.endswith(".xlsx")
            or file.filename.endswith(".xls")
        ):
            raise HTTPException(
                status_code=400, detail="Only CSV and Excel files are supported"
            )

        # Read file content
        contents = await file.read()

        # Parse file based on type
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))

        # Validate dataframe
        if df.empty:
            raise HTTPException(status_code=400, detail="File is empty")

        # Create session
        session_id = str(uuid.uuid4())
        sessions[session_id] = SessionData(session_id, df, file.filename)

        return {
            "session_id": session_id,
            "filename": file.filename,
            "rows": len(df),
            "columns": df.columns.tolist(),
            "preview": df.head(5).to_dict("records"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.post("/analyze")
async def analyze_duplicates(selection: ColumnSelection):
    """Analyze selected columns for semantic duplicates"""
    try:
        if model is None:
            raise HTTPException(
                status_code=503,
                detail="Model not loaded yet. Please try again in a few moments.",
            )

        if selection.session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        session = sessions[selection.session_id]
        session.selected_columns = selection.columns
        session.similarity_threshold = selection.similarity_threshold

        # Validate columns exist
        for col in selection.columns:
            if col not in session.original_df.columns:
                raise HTTPException(status_code=400, detail=f"Column '{col}' not found")

        # Combine selected columns into text for embedding
        df = session.original_df
        combined_text = df[selection.columns].astype(str).agg(" ".join, axis=1).tolist()

        # Generate embeddings
        print(f"Generating embeddings for {len(combined_text)} rows...")
        embeddings = model.encode(combined_text, show_progress_bar=True)
        session.embeddings = embeddings

        # Calculate cosine similarity matrix
        similarity_matrix = cosine_similarity(embeddings)

        # Find potential duplicates
        duplicate_groups = []
        processed_indices = set()

        for i in range(len(similarity_matrix)):
            if i in processed_indices:
                continue

            # Find similar items (excluding self)
            similar_indices = np.where(
                (similarity_matrix[i] >= selection.similarity_threshold)
                & (np.arange(len(similarity_matrix)) != i)
            )[0]

            if len(similar_indices) > 0:
                group_indices = [i] + similar_indices.tolist()
                processed_indices.update(group_indices)

                # Create duplicate group
                duplicate_id = str(uuid.uuid4())
                group = {"duplicate_id": duplicate_id, "rows": []}

                for idx in group_indices:
                    row_data = df.iloc[idx].to_dict()
                    row_data["original_index"] = int(idx)
                    row_data["similarity_scores"] = {
                        str(other_idx): float(similarity_matrix[idx][other_idx])
                        for other_idx in group_indices
                        if other_idx != idx
                    }
                    group["rows"].append(row_data)

                duplicate_groups.append(group)

        session.duplicate_groups = duplicate_groups

        return {
            "session_id": selection.session_id,
            "total_rows": len(df),
            "duplicate_groups": len(duplicate_groups),
            "total_potential_duplicates": sum(len(g["rows"]) for g in duplicate_groups),
            "groups": duplicate_groups,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error analyzing duplicates: {str(e)}"
        )


@app.post("/review")
async def review_duplicate(review: DuplicateReview):
    """Mark a duplicate group as true or false duplicate"""
    try:
        if review.session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        session = sessions[review.session_id]
        session.reviewed_duplicates[review.duplicate_id] = review.is_duplicate

        return {
            "session_id": review.session_id,
            "duplicate_id": review.duplicate_id,
            "is_duplicate": review.is_duplicate,
            "total_reviewed": len(session.reviewed_duplicates),
            "total_groups": len(session.duplicate_groups),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error reviewing duplicate: {str(e)}"
        )


@app.get("/export/{session_id}")
async def export_report(session_id: str):
    """Export multi-sheet Excel report"""
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        session = sessions[session_id]

        # Prepare output file
        output_path = f"/app/temp_data/{session_id}_report.xlsx"

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            # Sheet 1: Original Data
            session.original_df.to_excel(
                writer, sheet_name="Original Data", index=False
            )

            # Identify confirmed duplicates
            confirmed_duplicate_indices = set()
            duplicate_mapping = {}  # Maps index to its duplicate group

            for group in session.duplicate_groups:
                duplicate_id = group["duplicate_id"]
                is_confirmed = session.reviewed_duplicates.get(duplicate_id, False)

                if is_confirmed:
                    indices = [row["original_index"] for row in group["rows"]]
                    confirmed_duplicate_indices.update(
                        indices[1:]
                    )  # Keep first, mark rest as duplicates

                    # Map all indices to the first (canonical) index
                    canonical_idx = indices[0]
                    for idx in indices:
                        duplicate_mapping[idx] = canonical_idx

            # Sheet 2: De-duplicated Data
            deduplicated_df = session.original_df.drop(
                index=list(confirmed_duplicate_indices)
            ).reset_index(drop=True)
            deduplicated_df.to_excel(
                writer, sheet_name="De-duplicated Data", index=False
            )

            # Sheet 3: Duplicates Only
            duplicates_data = []
            for group in session.duplicate_groups:
                duplicate_id = group["duplicate_id"]
                is_confirmed = session.reviewed_duplicates.get(duplicate_id, False)

                if is_confirmed:
                    indices = [row["original_index"] for row in group["rows"]]
                    canonical_idx = indices[0]

                    for idx in indices:
                        row_data = session.original_df.iloc[idx].to_dict()
                        row_data["Original_Row_Index"] = idx
                        row_data["Canonical_Row_Index"] = canonical_idx
                        row_data["Is_Canonical"] = idx == canonical_idx
                        row_data["Duplicate_Group_ID"] = duplicate_id
                        duplicates_data.append(row_data)

            if duplicates_data:
                duplicates_df = pd.DataFrame(duplicates_data)
                duplicates_df.to_excel(writer, sheet_name="Duplicates", index=False)
            else:
                # Create empty sheet with headers
                pd.DataFrame(columns=["No confirmed duplicates"]).to_excel(
                    writer, sheet_name="Duplicates", index=False
                )

            # Sheet 4: Statistics
            total_potential_groups = len(session.duplicate_groups)
            total_reviewed = len(session.reviewed_duplicates)
            confirmed_true = sum(1 for v in session.reviewed_duplicates.values() if v)
            confirmed_false = sum(
                1 for v in session.reviewed_duplicates.values() if not v
            )
            total_potential_duplicates = sum(
                len(g["rows"]) for g in session.duplicate_groups
            )
            total_confirmed_duplicates = len(confirmed_duplicate_indices)

            stats_data = {
                "Metric": [
                    "Original Row Count",
                    "De-duplicated Row Count",
                    "Rows Removed",
                    "Potential Duplicate Groups Identified",
                    "Groups Reviewed",
                    "Groups Confirmed as Duplicates",
                    "Groups Confirmed as Non-Duplicates",
                    "Groups Pending Review",
                    "Total Rows in Potential Duplicate Groups",
                    "Total Confirmed Duplicate Rows (Removed)",
                    "Similarity Threshold Used",
                    "Columns Analyzed",
                ],
                "Value": [
                    len(session.original_df),
                    len(deduplicated_df),
                    total_confirmed_duplicates,
                    total_potential_groups,
                    total_reviewed,
                    confirmed_true,
                    confirmed_false,
                    total_potential_groups - total_reviewed,
                    total_potential_duplicates,
                    total_confirmed_duplicates,
                    session.similarity_threshold,
                    ", ".join(session.selected_columns),
                ],
            }

            stats_df = pd.DataFrame(stats_data)
            stats_df.to_excel(writer, sheet_name="Statistics", index=False)

        return FileResponse(
            path=output_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"{Path(session.filename).stem}_duplicate_report.xlsx",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating report: {str(e)}"
        )


@app.get("/session/{session_id}")
async def get_session_status(session_id: str):
    """Get current session status"""
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        session = sessions[session_id]

        return {
            "session_id": session_id,
            "filename": session.filename,
            "total_rows": len(session.original_df),
            "selected_columns": session.selected_columns,
            "duplicate_groups": len(session.duplicate_groups),
            "reviewed": len(session.reviewed_duplicates),
            "pending_review": len(session.duplicate_groups)
            - len(session.reviewed_duplicates),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching session: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
