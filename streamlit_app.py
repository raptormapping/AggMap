import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from math import radians, cos, sin, asin, sqrt

# ✅ Distance function
def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * asin(sqrt(a))

# ✅ Safe session state setup
st.session_state.setdefault("competitor_visibility", {})
st.session_state.setdefault("project_sites", {})
st.session_state.setdefault("all_competitors", set())
st.session_state.setdefault("last_radius", -1.0)

# === Page setup ===
st.set_page_config(page_title="Company Map Viewer", layout="wide")
st.title("📍 Integrated Company Map Viewer")

# === File upload ===
uploaded_file = st.file_uploader("Upload Excel file (with 'Companies' and 'Projects' sheets)", type=["xlsx"])

# === Add new project manually ===
st.sidebar.subheader("➕ Add a New Project Site")
new_name = st.sidebar.text_input("Project Name")
new_lat = st.sidebar.number_input("Latitude", format="%.6f", min_value=-90.0, max_value=90.0)
new_lon = st.sidebar.number_input("Longitude", format="%.6f", min_value=-180.0, max_value=180.0)
if st.sidebar.button("Add Project"):
    st.session_state.project_sites[new_name] = {"lat": new_lat, "lon": new_lon, "visible": True}
    st.success(f"Project '{new_name}' added!")

# === Radius controls ===
st.sidebar.subheader("🔎 Map Mode")
mode = st.sidebar.radio("Select Map Mode", ["All Companies with Radius", "Companies Within Radius of Project"])
st.sidebar.markdown("---")
radius_slider = st.sidebar.slider("Select radius (miles)", 1, 60, 10)
radius_manual = st.sidebar.number_input(
    "Or enter exact radius",
    min_value=1.0,
    max_value=500.0,
    value=float(radius_slider),
    step=1.0,
    format="%.2f"
)
radius_miles = radius_manual
radius_km = radius_miles * 1.60934

# === Load data ===
if uploaded_file:
    try:
        xls = pd.ExcelFile(uploaded_file, engine="openpyxl")
        companies_df = pd.read_excel(xls, "Companies")
        projects_df = pd.read_excel(xls, "Projects")

        required_cols = ['Company Location', 'Latitude', 'Longitude', 'Company Name']
        if not all(col in companies_df.columns for col in required_cols):
            st.error("❌ 'Companies' sheet must include: Company Location, Latitude, Longitude, Company Name")
        elif not all(col in projects_df.columns for col in ['Project Name', 'Latitude', 'Longitude']):
            st.error("❌ 'Projects' sheet must include: Project Name, Latitude, Longitude")
        else:
            if not st.session_state.project_sites:
                for _, row in projects_df.iterrows():
                    st.session_state.project_sites[row['Project Name']] = {
                        "lat": row['Latitude'], "lon": row['Longitude'], "visible": True
                    }

            st.sidebar.subheader("🛠 Manage Project Sites")
            to_delete = []
            for name, data in st.session_state.project_sites.items():
                col1, col2 = st.sidebar.columns([5, 1])
                visible = col1.checkbox(f"{name}", value=data["visible"], key=f"proj_{name}")
                st.session_state.project_sites[name]["visible"] = visible
                if col2.button("❌", key=f"remove_{name}"):
                    to_delete.append(name)
            for name in to_delete:
                del st.session_state.project_sites[name]

            for _, row in companies_df.iterrows():
                cname = row['Company Location']
                st.session_state.all_competitors.add(cname)
                if cname not in st.session_state.competitor_visibility:
                    st.session_state.competitor_visibility[cname] = True

            selected_project = None
            visible_projects = [p for p, v in st.session_state.project_sites.items() if v["visible"]]

            if mode == "Companies Within Radius of Project" and visible_projects:
                selected_project = visible_projects[0]
                proj_lat = st.session_state.project_sites[selected_project]["lat"]
                proj_lon = st.session_state.project_sites[selected_project]["lon"]
                companies_df['Distance (mi)'] = companies_df.apply(
                    lambda row: haversine(proj_lat, proj_lon, row['Latitude'], row['Longitude']), axis=1
                )

                if radius_miles != st.session_state.last_radius:
                    for _, row in companies_df.iterrows():
                        cname = row['Company Location']
                        st.session_state.competitor_visibility[cname] = row['Distance (mi)'] <= radius_miles
                    for pname, pdata in st.session_state.project_sites.items():
                        dist = haversine(proj_lat, proj_lon, pdata["lat"], pdata["lon"])
                        st.session_state.project_sites[pname]["visible"] = dist <= radius_miles
                    st.session_state.last_radius = radius_miles

            visible_competitors = [k for k, v in st.session_state.competitor_visibility.items() if v]
            visible_df = companies_df[companies_df['Company Location'].isin(visible_competitors)]

            company_names = companies_df['Company Name'].unique()
            colormap = plt.colormaps['tab20']
            company_colors = {
                name: mcolors.to_hex(colormap(i % colormap.N)) for i, name in enumerate(company_names)
            }

            col1, col2 = st.columns([3, 1])

            with col2:
                st.subheader("📘 Legend")
                legend_html = "<div style='background:white; border:2px solid grey; font-size:14px; padding:10px;'>"
                for name in sorted(company_names):
                    color = company_colors[name]
                    legend_html += f"<i style='background:{color}; width:12px; height:12px; display:inline-block; margin-right:8px;'></i>{name}<br>"
                legend_html += "</div>"
                st.markdown(legend_html, unsafe_allow_html=True)

                st.divider()
                st.subheader("🔘 Company Location Toggles")

                global_all_on = all(bool(st.session_state.competitor_visibility.get(c, True)) for c in st.session_state.all_competitors)
                if st.button("🌐 Deselect All" if global_all_on else "🌐 Select All"):
                    for c in st.session_state.all_competitors:
                        st.session_state.competitor_visibility[c] = not global_all_on

                grouped = companies_df.groupby("Company Name")
                for company, group in grouped:
                    with st.expander(f"📦 {company}", expanded=True):
                        all_checked = all(bool(st.session_state.competitor_visibility.get(row['Company Location'], True))
                                          for _, row in group.iterrows())
                        label = "Deselect All" if all_checked else "Select All"
                        if st.button(f"{label} ({company})"):
                            for _, row in group.iterrows():
                                cname = row['Company Location']
                                st.session_state.competitor_visibility[cname] = not all_checked

                        for _, row in group.iterrows():
                            cname = row['Company Location']
                            val = bool(st.session_state.competitor_visibility.get(cname, True))
                            updated = st.checkbox(cname, value=val, key=f"toggle_{cname}")
                            st.session_state.competitor_visibility[cname] = updated

            with col1:
                m = folium.Map(location=[visible_df['Latitude'].mean(), visible_df['Longitude'].mean()], zoom_start=10)

                for name, data in st.session_state.project_sites.items():
                    if data["visible"]:
                        lat, lon = data["lat"], data["lon"]
                        folium.Marker(
                            location=[lat, lon],
                            popup=f"<b>📍 {name}</b>",
                            icon=folium.Icon(color="red", icon="star", prefix="fa")
                        ).add_to(m)
                        if name == selected_project and mode == "Companies Within Radius of Project":
                            folium.Circle(
                                location=[lat, lon],
                                radius=radius_miles * 1609.34,
                                color="red", fill=True, fill_opacity=0.2
                            ).add_to(m)

                for _, row in visible_df.iterrows():
                    lat, lon = row['Latitude'], row['Longitude']
                    label = row['Company Location']
                    group = row['Company Name']
                    color = company_colors.get(group, '#000000')
                    popup = f"{label}"
                    if 'Distance (mi)' in row:
                        popup += f" ({round(row['Distance (mi)'], 2)} mi)"

                    # ✅ Blue star for Raptor Materials, black pin-drop for others
                    if group == "Raptor Materials":
                        folium.Marker(
                            location=[lat, lon],
                            popup=popup,
                            icon=folium.Icon(color="blue", icon="star", prefix="fa")
                        ).add_to(m)
                    else:
                        folium.Marker(
                            location=[lat, lon],
                            popup=popup,
                            icon=folium.Icon(color="black")
                        ).add_to(m)

                    folium.Circle(
                        location=[lat, lon],
                        radius=radius_km * 1000 if mode == "All Companies with Radius" else 200,
                        color=color, fill=True, fill_color=color, fill_opacity=0.3
                    ).add_to(m)

                st.subheader("🗺️ Interactive Map")
                st_folium(m, width=800, height=600)

    except Exception as e:
        st.error(f"❌ Error loading file: {e}")
else:
    st.info("⬆️ Please upload an Excel file with 'Companies' and 'Projects' sheets to get started.")
