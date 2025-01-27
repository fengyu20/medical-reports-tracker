const handleSubmit = async (event) => {
    event.preventDefault();
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('indicators', JSON.stringify(selectedIndicators));
  
    try {
      await uploadFile(formData);
      // Handle success
    } catch (error) {
      // Handle error
    }
  };