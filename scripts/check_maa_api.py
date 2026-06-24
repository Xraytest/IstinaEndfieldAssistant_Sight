import maa
print("=== Library ===")
for attr in ['open', 'version', 'framework_libpath']:
    val = getattr(maa.Library, attr, "N/A")
    if callable(val):
        print(f"  {attr}: <callable>")
    else:
        print(f"  {attr}: {val}")

print("\n=== Toolkit ===")
print(dir(maa.Library.toolkit))

print("\n=== define key types ===")
for name in sorted(dir(maa.define)):
    if name.startswith("Maa"):
        print(f"  {name}")