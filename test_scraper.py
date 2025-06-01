# real_estate_assistant/test_scraper.py
import asyncio
import os
import logging
from dotenv import load_dotenv
import json

# Import the updated PropertyRetriever and DistrictAnalyzer classes
from agents.property_retriever import PropertyRetriever
from agents.district_analyzer import DistrictAnalyzer
from langchain_together import ChatTogether

# Load environment variables from .env file
load_dotenv()

# Configure logging for detailed output during scraping
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_property_retriever():
    """Test the PropertyRetriever's real-time data collection with improved filtering"""
    logger.info("=== Testing PropertyRetriever Real-time Data Collection ===")

    together_api_key = os.getenv("TOGETHER_API_KEY")
    if not together_api_key:
        logger.error("TOGETHER_API_KEY not found in .env file. Please set it to run the scraper.")
        return

    dummy_llm = ChatTogether(
        together_api_key=together_api_key,
        model="meta-llama/Meta-Llama-3-70B-Instruct-Turbo",
        temperature=0.0
    )

    scraper = PropertyRetriever(llm=dummy_llm)

    try:
        # Test the vector data collection with improved filtering
        logger.info("🚀 Starting enhanced vector data collection...")
        logger.info("This will now properly filter residential apartments from other property types")

        collected_documents = await scraper.retrieve_vector_data()

        if collected_documents:
            logger.info(f"\n🎉 SUCCESS! Collected {len(collected_documents)} district documents")

            # Show summary of what was collected
            logger.info("\n📋 COLLECTED DATA SUMMARY:")
            for i, doc in enumerate(collected_documents, 1):
                lines = doc.page_content.split('\n')
                district_line = lines[0] if lines else "Unknown district"
                data_count_line = [line for line in lines if 'Цуглуулсан өгөгдөл' in line]
                data_count = data_count_line[0] if data_count_line else "No count info"

                logger.info(f"  {i}. {district_line}")
                logger.info(f"     {data_count}")

        else:
            logger.warning("❌ No documents were collected.")
            logger.info("This might be due to:")
            logger.info("- Network connectivity issues")
            logger.info("- All properties being filtered out as non-residential")
            logger.info("- Website structure changes")

        return collected_documents

    except Exception as e:
        logger.error(f"❌ Error during vector data collection: {e}", exc_info=True)
        return []

    finally:
        await scraper.close()


async def test_single_property_retrieval():
    """Test retrieving details from a single property URL"""
    logger.info("\n=== Testing Single Property Retrieval ===")

    together_api_key = os.getenv("TOGETHER_API_KEY")
    if not together_api_key:
        logger.error("TOGETHER_API_KEY not found.")
        return

    dummy_llm = ChatTogether(
        together_api_key=together_api_key,
        model="meta-llama/Meta-Llama-3-70B-Instruct-Turbo",
        temperature=0.0
    )

    scraper = PropertyRetriever(llm=dummy_llm)

    # Test with a sample URL (you might need to update this with a real URL)
    test_url = "https://www.unegui.mn/adv/9377936_encanto-tower-107-mkv-4-oroo/"

    try:
        logger.info(f"Testing single property retrieval from: {test_url}")
        property_details = await scraper.retrieve_property_details(test_url)

        logger.info("✅ Single property retrieval complete.")
        logger.info(f"Property Details:\n{json.dumps(property_details, indent=2, ensure_ascii=False)}")

        return property_details

    except Exception as e:
        logger.error(f"❌ Error during single property retrieval: {e}", exc_info=True)
        return {}

    finally:
        await scraper.close()


async def test_district_analyzer():
    """Test the DistrictAnalyzer with real-time data"""
    logger.info("\n=== Testing DistrictAnalyzer with Real-time Data ===")

    together_api_key = os.getenv("TOGETHER_API_KEY")
    if not together_api_key:
        logger.error("TOGETHER_API_KEY not found.")
        return

    llm = ChatTogether(
        together_api_key=together_api_key,
        model="meta-llama/Meta-Llama-3-70B-Instruct-Turbo",
        temperature=0.7
    )

    property_retriever = PropertyRetriever(llm=llm)
    district_analyzer = DistrictAnalyzer(llm=llm, property_retriever=property_retriever)

    try:
        logger.info("🔧 Initial vectorstore state (static data):")
        initial_summary = district_analyzer.get_all_districts_summary()
        logger.info(f"Initial districts: {initial_summary}")

        # Update with real-time data
        logger.info("\n🔄 Manually updating with real-time data...")
        update_success = await district_analyzer.update_with_realtime_data()

        if update_success:
            logger.info("✅ Real-time data update successful!")

            # Show new vectorstore state
            logger.info("\n📊 Updated vectorstore state (real-time data):")
            updated_summary = district_analyzer.get_all_districts_summary()
            logger.info(f"Updated districts: {updated_summary}")
        else:
            logger.warning("⚠️  Real-time data update failed, using static data")

        # Test district analysis
        test_districts = ["Баянзүрх", "Сүхбаатар", "хан-уул"]

        for district in test_districts:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"🏢 Testing analysis for: {district}")
            logger.info('=' * 60)

            try:
                analysis_result = await district_analyzer.analyze_district(district)
                logger.info(f"📋 Analysis Result for {district}:")
                logger.info(analysis_result)

                # Check if result contains real-time data indicators
                if 'Цуглуулсан өгөгдөл:' in analysis_result or any(
                        price > 1000000 for line in analysis_result.split('\n')
                        for word in line.split()
                        if word.replace(' ', '').replace('төгрөг', '').replace(',', '').isdigit()
                           and len(word.replace(' ', '').replace('төгрөг', '').replace(',', '')) > 6
                ):
                    logger.info("✅ This appears to use REAL-TIME data!")
                else:
                    logger.info("⚠️  This appears to use STATIC fallback data")

            except Exception as e:
                logger.error(f"❌ Error analyzing {district}: {e}")

        # Test districts summary
        logger.info(f"\n{'=' * 60}")
        logger.info("📊 Final Districts Summary")
        logger.info('=' * 60)
        summary = district_analyzer.get_all_districts_summary()
        logger.info(f"All districts summary:\n{summary}")

    except Exception as e:
        logger.error(f"❌ Error in DistrictAnalyzer test: {e}", exc_info=True)

    finally:
        await property_retriever.close()


async def main():
    """Main test function"""
    logger.info("🚀 Starting comprehensive real estate assistant tests...")

    # Test 1: PropertyRetriever vector data collection
    collected_docs = await test_property_retriever()

    # Test 2: Single property retrieval
    await test_single_property_retrieval()

    # Test 3: DistrictAnalyzer with real-time data
    await test_district_analyzer()

    logger.info("\n🎉 All tests completed!")

    # Summary
    if collected_docs:
        logger.info(f"✅ Successfully collected {len(collected_docs)} district documents")
    else:
        logger.warning("⚠️  No documents were collected - check your internet connection and unegui.mn availability")


if __name__ == "__main__":
    # Set debug logging for detailed output
    logging.getLogger('agents.property_retriever').setLevel(logging.DEBUG)
    logging.getLogger('agents.district_analyzer').setLevel(logging.DEBUG)

    # Run the comprehensive test
    asyncio.run(main())



