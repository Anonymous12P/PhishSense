import asyncio

from app.services.website_capture import WebsiteCaptureService


async def main():
    service = WebsiteCaptureService()

    result = await service.capture("https://github.com")

    print("=" * 60)

    for key, value in result.items():
        if key == "html":
            print("HTML Length:", len(value))
        else:
            print(f"{key}: {value}")

asyncio.run(main())