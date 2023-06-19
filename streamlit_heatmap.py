import logging
from pathlib import Path

# # log_file_path = Path("data/function_timings.log")
# log_file_path = Path.cwd() / "data" / "function_timings.log"
# # os.makedirs(log_file_path.parent, exist_ok=True)
# log_file_path.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    # filename=log_file_path,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

from streamlit_folium import folium_static
import numpy as np
import pandas as pd
import folium
from folium.plugins import MarkerCluster
import gspread
import psycopg2
import random
from datetime import date
from oauth2client.service_account import ServiceAccountCredentials
import gpt_heat_routes as hr
import io
import pickle
from googleapiclient.http import MediaIoBaseDownload
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# import SL_Access.gsheets as gs

SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive'
]
# Use Streamlit secrets for service account key



class GSheet:
    """This is a class for Google Worksheets."""

    def __init__(self, wrksht):
        self.wrksht = wrksht
        self.name = re.findall(r"'(.*?)'", str(wrksht))[0]
        df = pd.DataFrame(self.wrksht.get_all_values())
        df.columns = df.iloc[0]
        df.drop(0, inplace=True)
        self.df = df


class DB_Conn(object):
    """A class for establishing a connection with the database and Google Sheets."""

    def __init__(self):
        """Initialize the connection with the database and Google Sheets."""

        try:
            # create a parser
            db_cred = st.secrets["postgresql"]
            gs_cred = st.secrets["gs_cred"]  # "SL_Access/creds.json"
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ]
            self.conn = psycopg2.connect(**db_cred)
            creds_dict = st.secrets["gs_cred"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

            self.client = gspread.authorize(creds)
            self.cur = self.conn.cursor()
        except Exception as e:
            logging.error(f"Failed to connect to the database: {str(e)}")
            raise e  # Or handle this exception in a way that makes sense for your application

    def ex_query(self, query):
        """Execute the query and return a dataframe."""
        try:
            self.cur.execute(query)
            colnames = [desc[0] for desc in self.cur.description]
            rows = self.cur.fetchall()
            return pd.DataFrame(rows, columns=colnames)
        except Exception as e:
            logging.error(f"Failed to execute query: {str(e)}")
            raise e  # Or handle this exception in a way that makes sense for your application

    def close_conn(self):
        """Close the cursor and the connection."""
        try:
            self.cur.close()
            self.conn.close()
            print("PostgreSQL connection is closed")
        except Exception as e:
            logging.error(f"Failed to close connection: {str(e)}")
            raise e  # Or handle this exception in a way that makes sense for your application


def download_and_load_pickle(file_name):
    service_account_key = st.secrets["road_graphs"]
    credentials = Credentials.from_service_account_info(service_account_key, scopes=SCOPES)
    service = build('drive', 'v3', credentials=credentials)
    # Search for the file by name
    query = f"name='{file_name}'"
    results = service.files().list(q=query, fields="files(id, name)", supportsAllDrives=True).execute()
    items = results.get('files', [])

    # Check if the file is found
    if not items:
        print(f"The file '{file_name}' was not found.")
        return None

    # Get the file ID of the first matching file
    file_id = items[0]['id']

    # Download the file to memory
    request = service.files().get_media(fileId=file_id)
    file_buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(file_buffer, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

    # Load the pickle data from the memory buffer
    file_buffer.seek(0)
    road_graphs = pickle.load(file_buffer)
    return road_graphs


def find_geo_bounds(latitudes, longitudes):
    north, south, east, west = (
        np.max(latitudes) + 25,
        np.min(latitudes) - 25,
        np.max(longitudes) + 25,
        np.min(longitudes) - 25,
    )
    return north, south, east, west


def make_geo_filter(source_lat, source_long, border_lat, border_long):
    north, south, east, west = find_geo_bounds(border_lat, border_long)
    geo_filter = (
        (source_lat > min(north, south))
        & (source_lat < max(north, south))
        & (source_long > min(east, west))
        & (source_long < max(east, west))
    )
    return geo_filter


# @st.cache
def get_data():
    dbc = DB_Conn()
    if st.session_state.country == "West_Africa":
        # define set of countries for West Africa
        countries = {"Benin", "Sierra Leone", "Ghana"}
        # concatenate country names into a comma-separated string
        country_names = ", ".join([f"'{c}'" for c in countries])
        c_name = f"c.name IN ({country_names})"
    else:
        # retrieve country data from database for the specified country
        c_name = f"c.name = '{st.session_state.country}'"

    # retrieve country data from database for the specified country
    query = f"""
        SELECT irf.id as irf_id, irf.irf_number, irf.date_of_interception,
            irf.where_going_destination, irf.verified_evidence_categorization,
            bs.id as station_id, bs.station_name, bs.station_code, bs.operating_country_id,
            bs.latitude as tm_lat, bs.longitude as tm_long,
            p.id as person_id, p.address_notes, p.latitude as source_lat, p.longitude as source_long,
            c.id as country_id, c.latitude as country_lat, c.longitude as country_long,
            CASE
                WHEN irf.date_of_interception > '{st.session_state.start_date}' AND irf.date_of_interception < '{st.session_state.end_date}'
                    THEN 1
                ELSE 0
            END AS within_date_range
        FROM public.dataentry_irfcommon irf
        LEFT JOIN public.dataentry_intercepteecommon i ON irf.id = i.interception_record_id
        LEFT JOIN public.dataentry_person p ON i.person_id = p.id
        LEFT JOIN public.dataentry_borderstation bs ON irf.station_id = bs.id
        LEFT JOIN public.dataentry_country c ON bs.operating_country_id = c.id
        WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
            AND irf.irf_number IS NOT NULL
            AND irf.verified_evidence_categorization IS NOT NULL
            AND bs.latitude IS NOT NULL AND bs.longitude IS NOT NULL
            AND irf.date_of_interception > '{start_date}' AND irf.date_of_interception < '{end_date}'
            AND {c_name}
        GROUP BY irf.id, bs.id, p.id, c.id
    """
    # st.write(query)
    irfs = dbc.ex_query(query)
    if irfs.empty:
        # Handle the case when `irfs` is empty
        st.write("Warning: There is no data! Please try another country or date range")
        return None
    N, S, E, W = (
        np.max(irfs.tm_lat) + 25,
        np.min(irfs.tm_lat) - 25,
        np.max(irfs.tm_long) + 25,
        np.min(irfs.tm_long) - 25,
    )

    irfs = irfs[
        (irfs.source_lat > min(N, S))
        & (irfs.source_lat < max(N, S))
        & (irfs.source_long > min(E, W))
        & (irfs.source_long < max(E, W))
    ]
    dbc.close_conn()
    return irfs


# @st.cache
def add_tm_stations(M, df, lat="tm_lat", long="tm_long", station="station_name"):
    df = df.dropna(subset=[lat]).drop_duplicates(subset=[station]).reset_index()
    for i in range(len(df)):
        folium.Marker(
            [df[lat][i], df[long][i]],
            popup=df[station][i],
            icon=folium.Icon(color="green", icon="plus"),
        ).add_to(M)
    return M


def add_source_clusters(
    M, df, source_lat="source_lat", source_long="source_long", popup="irf_number"
):
    marker_cluster = MarkerCluster().add_to(M)
    # for i in range(len(df)):
    for i in df.index.values:
        folium.Marker(
            [df[source_lat][i], df[source_long][i]], popup=df[popup][i]
        ).add_to(marker_cluster)
    return M


def create_heatmap(irfs, show_tm_station_markers, show_pv_source_clusters, end_point):
    # TODO: Modify this function to create the heatmap based on your own data and requirements
    # Here we create a Folium heatmap with random data
    center = [0, 0]
    m = folium.Map(location=center, zoom_start=2)
    hm_data = [
        [random.uniform(-1, 1), random.uniform(-1, 1), 1] for _ in range(len(irfs))
    ]
    hm = folium.plugins.HeatMap(hm_data, name="Interception Points", control=False)
    hm.add_to(m)
    return m


# dc = DB_Conn()
dbc = DB_Conn()
pd.set_option("chained_assignment", None)
# Set up Streamlit app
st.title("Route Heatmap App")

# Get user input
country_options = [
    "Bangladesh",
    "Ghana",
    "India",
    "India Network",
    "Kenya",
    "Malawi",
    "Mozambique",
    "Namibia",
    "Nepal",
    "Rwanda",
    "Tanzania",
    "Uganda",
    "West_Africa",
    "Zimbabwe",
]
country = st.selectbox(
    "Select country:", options=country_options, key="country", help="Select country"
)
start_date = st.date_input(
    "Start date:",
    key="start_date",
    value=date(2019, 1, 1),
    min_value=date(2019, 1, 1),
    max_value=date(2023, 12, 31),
    help="Select a start date",
)
end_date = st.date_input(
    "End date:",
    key="end_date",
    value=date(2020, 1, 1),
    min_value=date(2019, 1, 1),
    max_value=date(2023, 12, 31),
    help="Select an end date",
)
show_transit_montoring_station_markers = st.checkbox(
    "Show TM Station markers",
    value=True,
    key="show_transit_montoring_station_markers",
    help="Show TM Station markers",
)
show_potential_victim_source_clusters = st.checkbox(
    "Show PV source clusters",
    value=True,
    key="show_potential_victim_source_clusters",
    help="Show PV source clusters",
)
end_point_options = ["transit_montoring_station", "destination"]
end_point = st.selectbox(
    "Select end point:",
    options=end_point_options,
    key="end_point",
    help="Select end point",
)

irfs = get_data()
if irfs is None:
    st.stop()

st.write("Retrieved {} data points".format(len(irfs)))
end_lat = "tm_lat"
end_long = "tm_long"
if st.session_state.end_point == "destination":
    workbook = dbc.client.open_by_url(
        "https://docs.google.com/spreadsheets/d/16uwSfc9Ptf6PeytjF0jvzljE15eqSq6r3FKdKiWjn08/edit#gid=0"
    )
    all_geo = GSheet(workbook.worksheet("Sheet1")).df
    irfs = pd.merge(
        irfs, all_geo, how="left", left_on="destination", right_on="Location"
    )

    irfs[["Lat", "Long"]] = irfs[["Lat", "Long"]].fillna(value=np.nan)
    irfs.loc[~irfs.Lat.isna(), "Lat"] = irfs.loc[~irfs.Lat.isna(), "Lat"].astype(float)
    irfs.loc[~irfs.Long.isna(), "Long"] = irfs.loc[~irfs.Long.isna(), "Long"].astype(
        float
    )

    geo_filter = make_geo_filter(irfs.Lat, irfs.Long, irfs.tm_lat, irfs.tm_long)
    irfs = irfs[geo_filter]
    irfs = irfs[~irfs[end_lat].isna()].reset_index(drop=True)

if country == "India Network":
    pickle_file = "India_Roads.p"
else:
    pickle_file = country + "_Roads.p"

road_graphs = download_and_load_pickle(pickle_file)

if len(irfs) > 1000:
    min_seg_count = np.ceil(np.log10(len(irfs)) ** 2)
elif len(irfs) > 500:
    min_seg_count = np.ceil(np.log10(len(irfs)))
else:
    min_seg_count = 1

route_heatmap = hr.get_route_heatmap(
    irfs,
    road_graphs,
    "irf_number",
    dest_lat=end_lat,
    dest_long=end_long,
    min_seg_count=min_seg_count,
)
# irfs.head(5).to_csv(Path('data/irfs.csv'))
if st.session_state.show_transit_montoring_station_markers:
    route_heatmap = add_tm_stations(route_heatmap, irfs, lat="tm_lat", long="tm_long")
# if st.session_state.show_potential_victim_source_clusters:
#     # irfs.to_csv(Path("data/irfs.csv"))
#     # route_heatmap = add_source_clusters(route_heatmap, irfs)
# st.write('Route heatmap:')

# st_data = st_folium(route_heatmap, width=725)

folium_static(route_heatmap, width=725)
# route_heatmap
