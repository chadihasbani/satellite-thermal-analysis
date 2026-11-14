"""Single-node satellite thermal analysis package.

Keep this module lightweight so Streamlit Community Cloud can import
`satellite_thermal.*` submodules without pulling the whole package graph
at startup. Import concrete APIs from the submodules that define them.
"""

__all__: list[str] = []
