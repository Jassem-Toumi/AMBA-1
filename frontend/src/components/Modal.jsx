import { useState, useEffect } from "react";
import PropTypes from "prop-types";

const Modal = ({
  modalInfo,
  handleDone,
  isDone,
  setIsDone,
  currentIdx,
  setCurrentIdx,
  handleCancel,
}) => {
  /* modalInfo is an an array of objects : an examle of an object:
    {
    title: "VPC",
    description: `Select an existing VPC or click on the "create new" button to create a new one`,
    data: vpcs,
    selectedData: selectedVpc,
    setSelectedData: setSelectedVpc,
    isOpen: isModalOpen,
    setIsOpen: setIsModalOpen,
  };
   OR more Generic:
    {
    title: string,
    description: string,
    data: array,
    selectedData: string,
    setSelectedData: function,
    isOpen: boolean,
    setIsOpen: function,
    };
    */

  // I wanto create a courousel of modals that will be displayed one after the other

  const handleNext = () => {
    if (currentIdx < modalInfo.length - 1) {
      setCurrentIdx(currentIdx + 1);
      if (currentIdx == modalInfo.length - 2) {
        setIsDone(true);
      } else {
        setIsDone(false);
      }
    }

    // if (currentIdx == modalInfo.length - 1) {
  };

  const handlePrevious = () => {
    if (currentIdx > 0) {
      setCurrentIdx(currentIdx - 1);
      setIsDone(false);
    }
  };

  return (
    <div
      className={`fixed m-0 inset-0 z-50 flex items-center justify-center bg-gray-900 bg-opacity-50 ${
        modalInfo[currentIdx].isOpen ? "block" : "hidden"
      }`}
    >
      <div className="w-1/2 p-8 bg-white rounded-lg shadow-md">
        <h1 className="text-2xl py-2 font-bold text-center">
          {modalInfo[currentIdx].title}
        </h1>
        <div className="space-y-4">
          {/* this is a dynamic DIV */}
          <div className="">
            <p className="py-5">
              {/* this is a dynamic description */}
              {modalInfo[currentIdx].description}
            </p>
            <div className="py-2 max-h-72 overflow-y-auto">
              {/* list of VPC's + each with an accordion input to select the VPC  and user can only select one at a time and once a button is selected change the background of the button to blue*/}
              <ul className="space-y-2 py-5">
                {modalInfo[currentIdx].data.map((item, index) => (
                  <li key={index}>
                    <button
                      className="w-full px-4 py-2 text-left border rounded-md border-awsOrange focus:outline-none"
                      onClick={() =>
                        modalInfo[currentIdx].setSelectedData(item)
                      }
                      style={{
                        backgroundColor:
                          modalInfo[currentIdx].selectedData === item
                            ? "#FFC46B"
                            : "white",
                      }}
                    >
                      {item}
                    </button>
                  </li>
                ))}
                <li>
                  <button
                    className="w-full px-4 py-2 text-left border rounded-md border-awsOrange focus:outline-none"
                    onClick={() =>
                      modalInfo[currentIdx].setSelectedData("create new")
                    }
                    style={{
                      backgroundColor:
                        modalInfo[currentIdx].selectedData === "create new"
                          ? "#FFC46B"
                          : "white",
                    }}
                  >
                    Create New
                  </button>
                </li>
              </ul>
            </div>
          </div>

          <div className="flex justify-end space-x-4">
            <button
              className="px-4 py-2 font-bold text-white bg-red-500 rounded-md hover:bg-red-600 focus:outline-none focus:ring focus:border-red-300"
              onClick={() => handleCancel()}
            >
              Cancel
            </button>
            {currentIdx > 0 && (
              <button
                className="px-4 py-2 font-bold text-white bg-blue-500 rounded-md hover:bg-blue-600 focus:outline-none focus:ring focus:border-blue-300"
                onClick={handlePrevious}
              >
                Previous
              </button>
            )}

            {isDone ? (
              <button
                className="px-4 py-2 font-bold text-white bg-green-500 rounded-md hover:bg-green-600 focus:outline-none focus:ring focus:border-green-300"
                onClick={handleDone}
              >
                Done
              </button>
            ) : (
              <button
                className="px-4 py-2 font-bold text-white bg-blue-500 rounded-md hover:bg-blue-600 focus:outline-none focus:ring focus:border-blue-300"
                onClick={handleNext}
              >
                Next
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

Modal.propTypes = {
  modalInfo: PropTypes.arrayOf(
    PropTypes.shape({
      title: PropTypes.string.isRequired,
      description: PropTypes.string.isRequired,
      data: PropTypes.array.isRequired,
      selectedData: PropTypes.string,
      setSelectedData: PropTypes.func,
      isOpen: PropTypes.bool.isRequired,
      setIsOpen: PropTypes.func.isRequired,
    })
  ).isRequired,
  handleDone: PropTypes.func.isRequired,
  isDone: PropTypes.bool.isRequired,
  setIsDone: PropTypes.func.isRequired,
  currentIdx: PropTypes.number.isRequired,
  setCurrentIdx: PropTypes.func.isRequired,
  handleCancel: PropTypes.func.isRequired,
};

export default Modal;
